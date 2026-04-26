"""
schemas/knowledge.py — Pydantic v2 schemas for the FlowDesk Knowledge Base.

Schema map:
  KnowledgeItem
  ├── KnowledgeItemCreate       POST /knowledge body (URL ingest)
  ├── KnowledgeItemPDFCreate    metadata alongside PDF upload (form fields)
  ├── KnowledgeItemUpdate       internal — used by the background worker to
  │                             write back extracted fields; NOT exposed as a
  │                             user-facing PATCH endpoint in Stage 4
  └── KnowledgeItemOut          full API response (single item)
      └── KnowledgeItemListOut  list item (drops raw_text — can be large)

  Collection (schema stub — endpoints in Stage 6)
  ├── CollectionCreate
  └── CollectionOut

  CollectionItem
  └── CollectionItemOut
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from models.knowledge import ContentType, ItemStatus, ReadStatus


# ---------------------------------------------------------------------------
# KnowledgeItem — user-facing create
# ---------------------------------------------------------------------------

class KnowledgeItemCreate(BaseModel):
    """POST /knowledge — URL ingestion."""
    url: str = Field(..., min_length=8, description="URL to ingest")
    tags: list[str] | None = Field(None, max_length=20)
    # If provided, item is added to this collection after creation
    collection_id: uuid.UUID | None = None
    is_priority: bool | None = None

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        # Lowercase, strip whitespace, deduplicate, max 50 chars each
        seen = set()
        result = []
        for tag in v:
            t = tag.strip().lower()[:50]
            if t and t not in seen:
                seen.add(t)
                result.append(t)
        return result or None

    model_config = ConfigDict(extra="forbid")


class KnowledgeItemPDFCreate(BaseModel):
    """
    Metadata sent alongside a PDF upload (as form fields, not JSON body).
    FastAPI reads these from Form() params in the route; Pydantic validates them.
    """
    tags: list[str] | None = None
    collection_id: uuid.UUID | None = None
    # User can optionally supply a title; otherwise we extract from PDF metadata
    title: str | None = Field(None, max_length=500)

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# KnowledgeItem — internal worker write-back
# ---------------------------------------------------------------------------

class KnowledgeItemWorkerUpdate(BaseModel):
    """
    Used exclusively by the background extraction worker to write results
    back to the DB. Never accepted from a user request.

    All fields are optional because extraction is incremental:
    title/cover_image come from metadata fetch, raw_text/summary come later.
    """
    title: str | None = None
    summary: str | None = None
    raw_text: str | None = None
    cover_image_url: str | None = None
    estimated_read_minutes: int | None = None
    is_processed: bool | None = None
    status: ItemStatus | None = None

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# KnowledgeItem — responses
# ---------------------------------------------------------------------------

class KnowledgeItemListOut(BaseModel):
    """
    Returned in the GET /knowledge list.

    raw_text is intentionally excluded — it can be megabytes for PDFs.
    The client fetches GET /knowledge/{id} when it needs the full text.
    """
    id: uuid.UUID
    user_id: uuid.UUID
    url: str | None
    title: str | None
    summary: str | None
    content_type: str
    cover_image_url: str | None
    estimated_read_minutes: int | None
    tags: list[str] | None
    is_processed: bool
    status: str
    is_priority: bool
    read_status: str
    read_at: datetime | None
    last_opened_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeItemOut(KnowledgeItemListOut):
    """
    Returned by GET /knowledge/{id} — adds raw_text.
    Inherits all fields from KnowledgeItemListOut.
    """
    raw_text: str | None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# KnowledgeItem — user-facing PATCH
# ---------------------------------------------------------------------------

class KnowledgeItemUpdate(BaseModel):
    """
    PATCH /knowledge/{id} — user-editable fields only.
    read_status accepts only READING and DONE (not UNREAD — use a dedicated
    mark-unread endpoint if that feature is added later).
    """
    title: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    tags: list[str] | None = None
    read_status: Literal["READING", "DONE"] | None = None
    is_priority: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "KnowledgeItemUpdate":
        if self.title is None and self.tags is None and self.read_status is None and self.is_priority is None:
            raise ValueError("PATCH body must contain at least one field")
        return self

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Collection schemas
# ---------------------------------------------------------------------------

class CollectionCreate(BaseModel):
    """POST /collections — create a custom collection."""
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    emoji: str | None = Field(None, max_length=8)

    model_config = ConfigDict(extra="forbid")


class CollectionUpdate(BaseModel):
    """PATCH /collections/{id} — rename, recolor, or re-emoji a collection."""
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    description: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    emoji: str | None = Field(None, max_length=8)

    @model_validator(mode="after")
    def at_least_one(self) -> "CollectionUpdate":
        if all(v is None for v in [self.name, self.description, self.color, self.emoji]):
            raise ValueError("PATCH body must contain at least one field")
        return self

    model_config = ConfigDict(extra="forbid")


class CollectionOut(BaseModel):
    """Full collection metadata — returned by list and single-collection endpoints."""
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    color: str | None
    emoji: str | None
    is_default: bool
    default_content_type: str | None
    # item_count and unread_count are computed by the router via subquery —
    # they are NOT stored columns, so we use a default of 0 for safety.
    item_count: int = 0
    unread_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollectionItemAdd(BaseModel):
    """POST /collections/{id}/items — add an existing item to a collection."""
    knowledge_item_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Read-status update
# ---------------------------------------------------------------------------

class ReadStatusUpdate(BaseModel):
    """PATCH /knowledge/{id}/read-status"""
    read_status: Literal["READING", "DONE"]

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Library endpoint schemas  (GET /library — single call, no N+1)
# ---------------------------------------------------------------------------

class LibraryItemPreview(BaseModel):
    """
    A minimal item card for the Library shelf preview.
    We only include fields needed to render a card — title, cover, type, status.
    Raw text is excluded (too large) and summary is excluded (not needed for shelf).
    """
    id: uuid.UUID
    url: str | None
    title: str | None
    cover_image_url: str | None
    content_type: str
    read_status: str
    estimated_read_minutes: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LibraryCollectionEntry(BaseModel):
    """
    One collection row in the Library response.
    items contains the first 10 items ordered by UNREAD first, then created_at DESC.
    This is populated by the router using a single JOIN query (not N+1).
    """
    id: uuid.UUID
    name: str
    description: str | None
    color: str | None
    emoji: str | None
    is_default: bool
    item_count: int = 0
    unread_count: int = 0
    # First 10 items for shelf preview — loaded eagerly in the library query
    items: list[LibraryItemPreview] = []

    model_config = ConfigDict(from_attributes=True)


class LibraryResponse(BaseModel):
    """
    Returned by GET /library.
    A single structured payload the Library page can render in one shot.
    total_unread is the sum across all collections for the badge count in the nav.
    """
    collections: list[LibraryCollectionEntry]
    total_items: int
    total_unread: int

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Ingest response (202 Accepted body)
# ---------------------------------------------------------------------------

class IngestAccepted(BaseModel):
    """
    Returned immediately by POST /knowledge and POST /knowledge/upload-pdf.
    The item exists in the DB with status="pending"; extraction runs async.
    """
    id: uuid.UUID
    status: str  # always "pending" at this point
    message: str = "Ingestion started. Poll GET /knowledge/{id} for status updates."

