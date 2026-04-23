"""
models/knowledge.py — FlowDesk Knowledge Base models.

Three models:
  KnowledgeItem   — the core ingested item (URL or PDF)
  Collection      — user-defined folder/grouping (Stage 6, added now for schema stability)
  CollectionItem  — M2M join between Collections and KnowledgeItems
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ContentType(str, enum.Enum):
    ARTICLE   = "article"
    YOUTUBE   = "youtube"
    GITHUB    = "github"
    TWITTER   = "twitter"
    LINKEDIN  = "linkedin"
    PDF       = "pdf"


class ItemStatus(str, enum.Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    DONE       = "done"
    FAILED     = "failed"


# ---------------------------------------------------------------------------
# KnowledgeItem
# ---------------------------------------------------------------------------

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Null for PDF uploads — PDFs have no source URL
    url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extracted from og:title / <title> / PDF metadata, or user-provided
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 2-sentence Gemini summary, written async after raw_text is populated
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # VARCHAR rather than a Postgres enum type — easier to add new types
    # without an ALTER TYPE migration
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Full extracted text for RAG (Stage 5). Stored here so we don't need a
    # separate table; for very large corpora you'd move this to object storage
    # and store only a reference. NULL until extraction completes.
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # og:image or YouTube thumbnail. Optional — many pages don't expose one.
    cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rough reading time computed from word count: words / 200 wpm.
    # NULL until extraction completes.
    estimated_read_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ARRAY(String) is Postgres-native. Stored as text[] — no separate tags table
    # needed at this stage. NULL means "no tags", not "empty array", to avoid
    # index bloat; application layer treats NULL and [] identically.
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )

    # Convenience flag — True once raw_text + summary are both populated.
    # Redundant with status == "done", but useful for quick boolean filters.
    is_processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # Processing pipeline state machine: pending → processing → done | failed
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ItemStatus.PENDING.value,
        server_default=ItemStatus.PENDING.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    owner = relationship("User", back_populates="knowledge_items", lazy="raise")
    collection_memberships = relationship(
        "CollectionItem", back_populates="knowledge_item",
        lazy="raise", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Primary list query: "all items for user, ordered by created_at DESC"
        # Covers the common case with no filters.
        Index("ix_ki_user_created", "user_id", "created_at"),

        # Filter by content_type (e.g. show only YouTube items)
        Index("ix_ki_user_content_type", "user_id", "content_type"),

        # Filter by status (e.g. show only failed items for retry UI)
        Index("ix_ki_user_status", "user_id", "status"),

        # Title search uses ILIKE — a plain btree index won't help here.
        # For production-scale search, replace with:
        #   Index("ix_ki_title_fts", func.to_tsvector("english", title),
        #         postgresql_using="gin")
        # For now the index is omitted; ILIKE on a per-user result set (small)
        # is fast enough without it.
    )

    def __repr__(self) -> str:
        return f"<KnowledgeItem id={str(self.id)[:8]} type={self.content_type} status={self.status}>"


# ---------------------------------------------------------------------------
# Collection  (Stage 6 — schema added now, endpoints added later)
# ---------------------------------------------------------------------------

class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 7-character hex color for UI (e.g. "#6366f1"). Nullable — UI falls back
    # to a default palette color when NULL.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    owner = relationship("User", back_populates="collections", lazy="raise")
    items = relationship(
        "CollectionItem", back_populates="collection",
        lazy="raise", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_collections_user_id", "user_id"),
    )


# ---------------------------------------------------------------------------
# CollectionItem  (M2M join table with metadata)
# ---------------------------------------------------------------------------

class CollectionItem(Base):
    """
    Explicit join table (not SQLAlchemy secondary=) because we carry
    metadata: added_at. This lets us order items within a collection by
    when they were added, not just by created_at on the item itself.
    """
    __tablename__ = "collection_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    collection    = relationship("Collection", back_populates="items", lazy="raise")
    knowledge_item = relationship("KnowledgeItem", back_populates="collection_memberships", lazy="raise")

    __table_args__ = (
        # The core constraint: an item can only be in a collection once.
        UniqueConstraint("collection_id", "knowledge_item_id", name="uq_collection_item"),

        # Fast lookup: "all items in collection X ordered by added_at"
        Index("ix_ci_collection_added", "collection_id", "added_at"),

        # Reverse lookup: "all collections containing item X" (for item detail view)
        Index("ix_ci_knowledge_item_id", "knowledge_item_id"),
    )


# ---------------------------------------------------------------------------
# Add to models/user.py:
# ---------------------------------------------------------------------------
#
#   knowledge_items = relationship(
#       "KnowledgeItem", back_populates="owner",
#       lazy="raise", cascade="all, delete-orphan"
#   )
#   collections = relationship(
#       "Collection", back_populates="owner",
#       lazy="raise", cascade="all, delete-orphan"
#   )
