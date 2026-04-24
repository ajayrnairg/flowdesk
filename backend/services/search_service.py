from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, cast
from pgvector.sqlalchemy import Vector

from models.knowledge_chunk import KnowledgeChunk
from models.knowledge import KnowledgeItem
from services.embedding_service import embed_query

async def semantic_search(query: str, user_id: UUID, db: AsyncSession, top_k: int = 5) -> list[dict]:
    """
    Vector search utilizing pgvector to find the most relevant document chunks.
    """
    # a. Embed the user's query
    query_vector = await embed_query(query)
    
    # b. Run pgvector cosine distance search
    # Cosine distance = 1 - cosine similarity. Lower distance is better.
    # Casting to Vector(768) ensures pgvector uses the correct index dimensions.
    stmt = (
        select(
            KnowledgeChunk,
            func.cosine_distance(
                KnowledgeChunk.embedding,
                cast(query_vector, Vector(768))
            ).label("distance")
        )
        .where(KnowledgeChunk.user_id == user_id)
        .where(KnowledgeChunk.embedding.is_not(None))
        .order_by("distance")
        .limit(top_k)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    if not rows:
        return []

    # c. Fetch parent items in a single query to avoid N+1 issues
    # Extract unique parent item IDs from the search results
    parent_ids = {row.KnowledgeChunk.knowledge_item_id for row in rows}
    
    item_stmt = select(KnowledgeItem).where(KnowledgeItem.id.in_(parent_ids))
    item_result = await db.execute(item_stmt)
    
    # Map item_id -> KnowledgeItem object for O(1) lookups
    item_map = {item.id: item for item in item_result.scalars().all()}

    # d. Format results into plain dictionaries
    formatted_results = []
    for row in rows:
        chunk = row.KnowledgeChunk
        distance = row.distance
        parent_item = item_map.get(chunk.knowledge_item_id)
        
        if not parent_item:
            continue
            
        formatted_results.append({
            "chunk_text": chunk.chunk_text,
            "chunk_index": chunk.chunk_index,
            "distance": float(distance),
            "knowledge_item_id": chunk.knowledge_item_id,
            "item_title": parent_item.title or "Untitled",
            "item_url": parent_item.url,
            "item_content_type": parent_item.content_type,
            "chunk_excerpt": chunk.chunk_text[:200]
        })

    return formatted_results