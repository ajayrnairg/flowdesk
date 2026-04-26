import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Integer, Index, UniqueConstraint, Enum as SAEnum
from sqlalchemy.sql import expression
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY
from core.database import Base

class ContentType(str, enum.Enum):
    ARTICLE   = "article"
    YOUTUBE   = "youtube"
    GITHUB    = "github"
    TWITTER   = "twitter"
    LINKEDIN  = "linkedin"
    PDF       = "pdf"

class ItemStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"

class ReadStatus(str, enum.Enum):
    UNREAD  = "UNREAD"
    READING = "READING"
    DONE    = "DONE"

class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    cover_image_url: Mapped[str] = mapped_column(String, nullable=True)
    estimated_read_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    status: Mapped[str] = mapped_column(String, default=ItemStatus.PENDING.value)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Reading progress ──────────────────────────────────────────────────
    read_status: Mapped[str] = mapped_column(
        SAEnum(ReadStatus, name="read_status", native_enum=False, create_type=False),
        nullable=False,
        default=ReadStatus.UNREAD.value,
        server_default=ReadStatus.UNREAD.value,
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="knowledge_items")
    collections = relationship("CollectionItem", back_populates="knowledge_item", cascade="all, delete-orphan")
    chunks = relationship(
        "KnowledgeChunk",
        back_populates="knowledge_item",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    __table_args__ = (
        Index("ix_knowledge_items_user_status", "user_id", "status"),
        Index("ix_knowledge_items_user_ctype", "user_id", "content_type"),
        Index("ix_knowledge_items_user_read_status", "user_id", "read_status"),
    )

class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Visual identity
    color: Mapped[str] = mapped_column(String(7), nullable=True)      # hex e.g. "#6366f1"
    emoji: Mapped[str] = mapped_column(String(8), nullable=True)      # e.g. "📰"

    # Auto-collections: created once per user per content_type, never duplicated.
    # is_default=True means it was system-created and cannot be deleted by the user.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=expression.false(), nullable=False)
    # Stores the content_type this default collection maps to (NULL for custom collections).
    default_content_type: Mapped[str] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items = relationship("CollectionItem", back_populates="collection", cascade="all, delete-orphan")

    __table_args__ = (
        # Guarantees only one default collection per content_type per user.
        # NULL default_content_type (custom collections) is excluded from this constraint
        # by the WHERE clause — but that requires a partial unique index, which we
        # handle at the application layer via get_or_create_default_collection.
        Index("ix_collections_user_id", "user_id"),
    )

class CollectionItem(Base):
    __tablename__ = "collection_items"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    collection_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    collection = relationship("Collection", back_populates="items")
    knowledge_item = relationship("KnowledgeItem", back_populates="collections")

    __table_args__ = (
        UniqueConstraint("collection_id", "knowledge_item_id", name="uq_collection_item"),
    )
