import time
import asyncio
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from routers.auth import get_current_user
from models.user import User
from models.knowledge import KnowledgeItem

from schemas.search import SearchRequest, SearchResponse, SearchSource
from services.search_service import semantic_search
from services.synthesis_service import synthesise_answer
from services.cache_service import get_cached_search, cache_search_result
from services.rag_indexer import index_knowledge_item

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

@router.post("", response_model=SearchResponse)
async def perform_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Performs a semantic search against the user's knowledge base and synthesizes an answer.
    Utilizes a cache-aside pattern via Upstash Redis to speed up repeated queries.
    """
    # Record start time for latency tracking
    start = time.monotonic()
    
    # Step 1: Check cache using the cache-aside pattern
    cached_data = await get_cached_search(current_user.id, request.query)
    
    if cached_data:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return SearchResponse(
            **cached_data,
            cached=True,
            took_ms=elapsed_ms
        )
    
    # Step 2: Run semantic search
    try:
        chunks = await semantic_search(request.query, current_user.id, db)
    except Exception as e:
        logger.error(f"Semantic search failed for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is currently unavailable. Please try again later."
        )
        
    # Step 3: Synthesise answer
    # (synthesise_answer internally catches exceptions and returns a graceful degradation message)
    answer = await synthesise_answer(request.query, chunks)
    
    # Step 4: Build response
    sources = [
        SearchSource(
            knowledge_item_id=c["knowledge_item_id"],
            title=c["item_title"],
            content_type=c["item_content_type"],
            url=c["item_url"],
            chunk_excerpt=c["chunk_excerpt"],
            # Convert cosine distance (0 to 2) to similarity score (higher is better)
            similarity_score=round(1.0 - c["distance"], 4)
        ) for c in chunks
    ]
    
    elapsed_ms = int((time.monotonic() - start) * 1000)
    
    response = SearchResponse(
        query=request.query,
        answer=answer,
        sources=sources,
        cached=False,
        took_ms=elapsed_ms
    )
    
    # Step 5: Cache the result (Fire and forget)
    # We explicitly exclude the metadata (`cached`, `took_ms`) from the dump so it stays accurate 
    # when we re-hydrate it on the next cache hit.
    asyncio.create_task(
        cache_search_result(
            current_user.id, 
            request.query, 
            response.model_dump(exclude={"cached", "took_ms"})
        )
    )
    
    return response

@router.get("/reindex/{item_id}")
async def reindex_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Forces a synchronous re-indexing of a knowledge item.
    Useful for items that were saved before the RAG pipeline was deployed.
    """
    # Verify ownership
    stmt = select(KnowledgeItem).where(
        KnowledgeItem.id == item_id,
        KnowledgeItem.user_id == current_user.id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        
    # Block and wait for indexing since the user explicitly requested it
    await index_knowledge_item(item.id, db)
    
    return {"status": "reindexed", "item_id": str(item_id)}