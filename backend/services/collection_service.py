"""
services/collection_service.py

Auto-collection logic for FlowDesk.

Each content type maps to exactly one named default collection per user.
get_or_create_default_collection() is idempotent — calling it N times
for the same (user_id, content_type) never creates duplicates.

Why a service, not inline router logic?
  - The ingestion orchestrator (background task) needs to call this too,
    so it must be importable outside the router module.
  - Keeping the SELECT + INSERT logic centralized avoids accidental drift.
"""

import uuid
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models.knowledge import Collection, CollectionItem, KnowledgeItem, ContentType, ReadStatus
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Default collection definitions ───────────────────────────────────────────
# content_type → (display_name, emoji, hex_color)
# twitter and linkedin both map to "Social Saves", so they share a slot.
# We key the dict by the DB content_type string.

DEFAULT_COLLECTIONS: dict[str, tuple[str, str, str]] = {
    ContentType.ARTICLE.value:  ("Articles",    "📰", "#6366f1"),  # indigo
    ContentType.YOUTUBE.value:  ("Videos",      "🎬", "#ef4444"),  # red
    ContentType.GITHUB.value:   ("Repos & Docs","🐙", "#22c55e"),  # green
    ContentType.TWITTER.value:  ("Social Saves","💬", "#0ea5e9"),  # sky
    ContentType.LINKEDIN.value: ("Social Saves","💬", "#0ea5e9"),  # same bucket
    ContentType.PDF.value:      ("PDFs",        "📄", "#f59e0b"),  # amber
}

# twitter and linkedin share one collection — canonical type to create under
SHARED_SOCIAL_TYPE = ContentType.TWITTER.value


async def get_or_create_default_collection(
    user_id: uuid.UUID,
    content_type: str,
    db: AsyncSession,
) -> Collection:
    """
    Finds or creates the default system collection for a given (user, content_type).

    Idempotency guarantee:
      SELECT first. Only INSERT if the SELECT returns None.
      The app-layer idempotency is sufficient here because this function is called
      from a single background task worker (no concurrent racing inserts for the
      same user/content_type pair in the same request lifecycle).

    twitter and linkedin are coalesced to the same "Social Saves" collection,
    keyed under content_type="twitter" in the database.
    """
    # Coalesce linkedin → twitter so they share one collection
    effective_type = SHARED_SOCIAL_TYPE if content_type == ContentType.LINKEDIN.value else content_type

    stmt = select(Collection).where(
        Collection.user_id == user_id,
        Collection.is_default == True,
        Collection.default_content_type == effective_type,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return existing

    # First time this user saves this content type — create the default collection
    name, emoji, color = DEFAULT_COLLECTIONS.get(
        effective_type,
        ("Saved Items", "📌", "#94a3b8")  # fallback for unknown types
    )

    collection = Collection(
        user_id=user_id,
        name=name,
        emoji=emoji,
        color=color,
        is_default=True,
        default_content_type=effective_type,
    )
    db.add(collection)
    await db.flush()  # Flush to get the generated id without committing
    logger.info(f"Created default collection '{name}' for user {user_id}")
    return collection


async def add_item_to_collection(
    collection_id: uuid.UUID,
    knowledge_item_id: uuid.UUID,
    db: AsyncSession,
) -> CollectionItem | None:
    """
    Adds a KnowledgeItem to a Collection.
    Returns None (no-op) if the item is already in the collection.
    Caller is responsible for committing the session.
    """
    stmt = select(CollectionItem).where(
        CollectionItem.collection_id == collection_id,
        CollectionItem.knowledge_item_id == knowledge_item_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return None  # Already in collection — idempotent no-op

    ci = CollectionItem(
        collection_id=collection_id,
        knowledge_item_id=knowledge_item_id,
    )
    db.add(ci)
    return ci
