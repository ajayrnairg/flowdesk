import asyncio
import sys
import os

# Ensure the backend directory is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

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
            print("Querying for a suitable KnowledgeItem...")
            stmt = select(KnowledgeItem).where(
                KnowledgeItem.status == "done",
                KnowledgeItem.raw_text.is_not(None),
                KnowledgeItem.raw_text != ""
            ).limit(1)
            
            result = await session.execute(stmt)
            item = result.scalar_one_or_none()
            
            if not item:
                print("No suitable KnowledgeItem found in the database. Please add one first.")
                return

            print(f"Found item: ID={item.id}, Title='{item.title}'")
            print("Running full indexing pipeline...")
            
            # Run the indexer (which handles fetching, chunking, embedding, and inserting)
            await index_knowledge_item(item.id, session)
            
            print("Indexing completed. Querying for resulting chunks...")
            
            # Fetch chunks created by the indexer
            chunk_stmt = select(KnowledgeChunk).where(
                KnowledgeChunk.knowledge_item_id == item.id
            ).order_by(KnowledgeChunk.chunk_index)
            
            chunk_result = await session.execute(chunk_stmt)
            chunks = chunk_result.scalars().all()
            
            print(f"Number of chunks created: {len(chunks)}")
            
            if not chunks:
                print("ERROR: No chunks were saved to the database.")
                print("Full pipeline FAILED")
                return
                
            first_chunk = chunks[0]
            excerpt = first_chunk.chunk_text[:100]
            # Replace newlines for cleaner printing
            excerpt = excerpt.replace('\n', ' ')
            safe_excerpt = excerpt.encode('ascii', 'replace').decode('ascii')
            print(f"First chunk text: '{safe_excerpt}...'")
            
            emb_len = len(first_chunk.embedding)
            print(f"Embedding length of first chunk: {emb_len}")
            
            if emb_len == 768:
                print("Full pipeline PASSED")
            else:
                print("Full pipeline FAILED")
                
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
