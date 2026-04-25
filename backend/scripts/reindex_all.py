import asyncio
import sys
import os

# Ensure the backend directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import func

from core.config import settings
import models.user
import models.task
import models.notification
import models.knowledge_chunk
from models.knowledge import KnowledgeItem
from models.knowledge_chunk import KnowledgeChunk
from services.rag_indexer import index_knowledge_item

async def main():
    print("Connecting to database...")
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # Get initial chunk count
            initial_chunk_count = await session.scalar(select(func.count(KnowledgeChunk.id)))
            
            print("Querying for KnowledgeItems that need indexing...")
            
            # Query items with status="done", non-empty raw_text, and 0 chunks
            stmt = (
                select(KnowledgeItem)
                .outerjoin(KnowledgeChunk, KnowledgeItem.id == KnowledgeChunk.knowledge_item_id)
                .where(
                    KnowledgeItem.status == "done",
                    KnowledgeItem.raw_text.is_not(None),
                    KnowledgeItem.raw_text != ""
                )
                .group_by(KnowledgeItem.id)
                .having(func.count(KnowledgeChunk.id) == 0)
            )
            
            result = await session.execute(stmt)
            items_to_index = result.scalars().all()
            total = len(items_to_index)
            
            if total == 0:
                print("No items need reindexing.")
                return
                
            print(f"Found {total} items to index.")
            
            for i, item in enumerate(items_to_index, 1):
                title = item.title or "Untitled"
                print(f"Indexing item {i}/{total}: {title}")
                
                try:
                    await index_knowledge_item(item.id, session)
                except Exception as e:
                    print(f"Failed to index item {item.id}: {e}")
                
                # Respect 100 req/min rate limit
                if i < total:
                    await asyncio.sleep(1)
            
            # Get final chunk count
            final_chunk_count = await session.scalar(select(func.count(KnowledgeChunk.id)))
            chunks_created = final_chunk_count - initial_chunk_count
            
            print(f"\nReindexed {total} items, {chunks_created} total chunks created")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
