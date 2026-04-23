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
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from models.knowledge import ContentType, ItemStatus


# ---------------------------------------------------------------------------
# KnowledgeItem — user-facing create
# ---------------------------------------------------------------------------

class KnowledgeItemCreate(BaseModel):
    """POST /knowledge — URL ingestion."""
    url: str = Field(..., min_length=8, description="URL to ingest")
    tags: list[str] | None = Field(None, max_length=20)
    # If provided, item is added to this collection after creation
    collection_id: uuid.UUID | None = None

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
# Collection schemas (stub — full endpoints in Stage 6)
# ---------------------------------------------------------------------------

class CollectionCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = None
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")

    model_config = ConfigDict(extra="forbid")


class CollectionOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    color: str | None
    created_at: datetime
    # item_count populated via a separate COUNT query in the router
    item_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CollectionItemOut(BaseModel):
    id: uuid.UUID
    collection_id: uuid.UUID
    knowledge_item_id: uuid.UUID
    added_at: datetime

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
