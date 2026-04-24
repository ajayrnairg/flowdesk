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
from services.chunking_service import chunk_text
from services.embedding_service import embed_texts

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
            
            chunks = chunk_text(item.raw_text)
            print(f"Produced {len(chunks)} chunks.")
            
            if not chunks:
                print("No chunks produced from raw_text.")
                return
                
            chunks_to_embed = chunks[:3]
            print(f"Embedding {len(chunks_to_embed)} chunks...")
            
            embeddings = await embed_texts(chunks_to_embed)
            
            print(f"Received {len(embeddings)} embeddings.")
            
            all_valid = True
            for i, emb in enumerate(embeddings):
                print(f"Chunk {i+1} embedding length: {len(emb)}")
                if len(emb) != 768:
                    all_valid = False
                    print(f"ERROR: Chunk {i+1} has length {len(emb)}, expected 768.")
            
            if len(embeddings) != len(chunks_to_embed):
                all_valid = False
                print(f"ERROR: Expected {len(chunks_to_embed)} embeddings, got {len(embeddings)}")
                
            if all_valid:
                print("Embedding test PASSED")
            else:
                print("Embedding test FAILED")
                
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
