import logging
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from models.knowledge import KnowledgeItem
from models.knowledge_chunk import KnowledgeChunk
from services.chunking_service import chunk_text
from services.embedding_service import embed_texts

logger = logging.getLogger(__name__)

async def index_knowledge_item(item_id: UUID, db: AsyncSession):
    """
    Background worker that chunks, embeds, and indexes a completed KnowledgeItem.
    """
    try:
        # a. Fetch the parent item
        stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()
        
        if not item:
            logger.warning(f"RAG Indexer: Item {item_id} not found.")
            return

        # b. Ensure text exists
        if not item.raw_text:
            logger.warning(f"RAG Indexer: Item {item_id} has no raw text to index.")
            return

        # c. Clean up existing chunks (supports re-indexing updated items)
        delete_stmt = delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_item_id == item.id)
        await db.execute(delete_stmt)
        # Flush to ensure deletes apply before we insert new ones
        await db.flush()

        # d. Chunk the text
        chunks = chunk_text(item.raw_text)
        if not chunks:
            logger.warning(f"RAG Indexer: Item {item_id} produced no valid chunks.")
            return

        # e. Embed the chunks
        embeddings = await embed_texts(chunks)

        # f & g. Create and persist KnowledgeChunk rows
        chunk_objects = []
        for idx, (chunk_content, embedding_vector) in enumerate(zip(chunks, embeddings)):
            chunk_row = KnowledgeChunk(
                knowledge_item_id=item.id,
                user_id=item.user_id,
                chunk_index=idx,
                chunk_text=chunk_content,
                embedding=embedding_vector
            )
            chunk_objects.append(chunk_row)

        db.add_all(chunk_objects)
        await db.commit()
        
        # h. Log success
        logger.info(f"Indexed {len(chunks)} chunks for item {item_id}")

    except Exception as e:
        # We do not re-raise because this is a background task. Crashing here
        # shouldn't take down the main worker loop.
        logger.exception(f"Failed to index knowledge item {item_id}: {e}")