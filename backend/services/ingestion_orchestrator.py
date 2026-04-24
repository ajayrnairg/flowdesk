from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.knowledge import KnowledgeItem, ItemStatus
from services.jina_extractor import fetch_with_jina, estimate_read_minutes
from services.youtube_extractor import fetch_youtube_content
from services.github_extractor import fetch_github_content
from services.gemini_summariser import generate_summary
from services.rag_indexer import index_knowledge_item
import logging

logger = logging.getLogger(__name__)

async def run_summary_only(item_id: UUID, db: AsyncSession):
    """
    A lightweight background task for items that already have raw_text extracted
    (e.g., PDF uploads and Bookmarklet clips).
    Only generates the Gemini summary and marks the item as DONE.
    """
    try:
        stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        
        if not item or not item.raw_text:
            return

        # Generate 2-sentence summary
        summary = await generate_summary(item.title or "Untitled", item.raw_text, item.content_type)
        
        item.summary = summary
        item.is_processed = True
        item.status = ItemStatus.DONE.value
        item.updated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        try:
            logger.info(f"Starting RAG indexing for item {item.id}")
            await index_knowledge_item(item.id, db)
        except Exception as e:
            logger.error(f"Failed to index item {item.id}, but ingestion completed: {e}")
    except Exception as e:
        # Fallback error handling
        try:
            stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
            result = await db.execute(stmt)
            item = result.scalar_one_or_none()
            if item:
                item.status = ItemStatus.FAILED.value
                item.updated_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception:
            pass

async def run_ingestion_pipeline(item_id: UUID, db: AsyncSession):
    """
    The background worker task. Orchestrates extraction, summary, and DB updates.
    Must never crash unhandled, always updating the DB status.
    """
    try:
        # 1. Fetch item & mark as processing
        stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        
        if not item:
            return # Item deleted before processing began
            
        item.status = ItemStatus.PROCESSING.value
        await db.commit()

        # 2. Extract content based on type
        ext_result = {}
        if item.content_type == "youtube":
            ext_result = await fetch_youtube_content(item.url)
            
        elif item.content_type == "github":
            ext_result = await fetch_github_content(item.url)
            # Fallback to Jina if the GitHub API fails or URL was weird
            if "error" in ext_result and ext_result["error"] == "invalid_github_url":
                ext_result = await fetch_with_jina(item.url)
                
        elif item.content_type == "pdf":
            # PDF text is already extracted at upload time in a real scenario
            # (or run via a separate queue). Skip extraction here.
            pass 
            
        elif item.content_type in ("twitter", "linkedin"):
            if not item.raw_text:
                ext_result = {"error": "Use bookmarklet for Twitter/LinkedIn"}
                
        else: # "article"
            ext_result = await fetch_with_jina(item.url)

        # 3. Handle Extractor Errors
        if "error" in ext_result:
            # We don't overwrite user's title with empty strings on failure
            item.status = ItemStatus.FAILED.value
            item.is_processed = False
            item.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return

        # 4. Apply Extracted Data
        if not item.title and ext_result.get("title"):
            item.title = ext_result.get("title")
            
        if ext_result.get("raw_text"):
            item.raw_text = ext_result.get("raw_text")
            item.estimated_read_minutes = estimate_read_minutes(item.raw_text)
            
        if ext_result.get("cover_image_url"):
            item.cover_image_url = ext_result.get("cover_image_url")
            
        item.is_processed = True

        # 5. Generate Summary
        if item.title and item.raw_text:
            summary = await generate_summary(item.title, item.raw_text, item.content_type)
            item.summary = summary

        # 6. Finalize Success Status
        item.status = ItemStatus.DONE.value
        item.updated_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            logger.info(f"Starting RAG indexing for item {item.id}")
            await index_knowledge_item(item.id, db)
        except Exception as e:
            logger.error(f"Failed to index item {item.id}, but ingestion completed: {e}")

    except Exception as e:
        # Catch-all failsafe: ensure item does not get stuck in 'processing'
        try:
            stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
            result = await db.execute(stmt)
            fallback_item = result.scalar_one_or_none()
            if fallback_item:
                fallback_item.status = ItemStatus.FAILED.value
                fallback_item.updated_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception:
            pass # DB connection might be broken, nothing we can do here