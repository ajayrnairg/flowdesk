import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.knowledge import Collection, CollectionItem

logger = logging.getLogger(__name__)

# Predefined auto-collection configurations
PREDEFINED_COLLECTIONS = {
    "article":  {"name": "📰 Articles",      "color": "#3B82F6"},
    "youtube":  {"name": "🎥 Videos",        "color": "#EF4444"},
    "github":   {"name": "💻 Repos & Docs",  "color": "#6B7280"},
    "twitter":  {"name": "💬 Social Saves",  "color": "#8B5CF6"},
    "linkedin": {"name": "💬 Social Saves",  "color": "#8B5CF6"},
    "pdf":      {"name": "📄 PDFs",          "color": "#F97316"},
}

async def get_or_create_default_collection(
    user_id: uuid.UUID, content_type: str, db: AsyncSession
) -> Collection:
    """
    Finds or creates the default system collection for a given content type.
    Safe for concurrent execution.
    """
    # Fallback to article config if unknown
    config = PREDEFINED_COLLECTIONS.get(content_type, PREDEFINED_COLLECTIONS["article"])
    target_name = config["name"]

    # 1. SELECT first to avoid duplicate insertions
    stmt = select(Collection).where(
        Collection.user_id == user_id,
        Collection.name == target_name
    ).limit(1)
    
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()

    if collection:
        return collection

    # 2. If not found, create the default collection
    collection = Collection(
        user_id=user_id,
        name=target_name,
        color=config["color"],
        is_default=True,
        # Both twitter and linkedin map to "twitter" functionally for the default_content_type
        default_content_type="twitter" if content_type in ["twitter", "linkedin"] else content_type,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    
    logger.info(f"Created default collection '{target_name}' for user {user_id}")
    return collection

async def auto_add_to_collection(
    knowledge_item_id: uuid.UUID, user_id: uuid.UUID, content_type: str, db: AsyncSession
) -> None:
    """
    Automatically routes a newly ingested item to its corresponding default collection.
    Completely isolated via try/except so it never breaks the ingestion pipeline.
    """
    try:
        collection = await get_or_create_default_collection(user_id, content_type, db)

        # Check if the relationship already exists
        stmt = select(CollectionItem).where(
            CollectionItem.collection_id == collection.id,
            CollectionItem.knowledge_item_id == knowledge_item_id
        ).limit(1)
        
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            # Create the M2M join row
            ci = CollectionItem(
                collection_id=collection.id,
                knowledge_item_id=knowledge_item_id
            )
            db.add(ci)
            await db.commit()
            
    except Exception as e:
        logger.error(f"Auto-collection failed for item {knowledge_item_id}: {e}")