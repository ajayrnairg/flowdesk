"""
routers/knowledge.py — FlowDesk Knowledge Base Ingestion API.

Endpoint map
────────────
POST   /knowledge                  Ingest a URL → 202 Accepted
POST   /knowledge/upload-pdf       Ingest a PDF → 202 Accepted
GET    /knowledge                  List items (filters: content_type, status, search)
GET    /knowledge/{item_id}        Get single item with raw_text
DELETE /knowledge/{item_id}        Hard delete

202 pattern
───────────
Both ingest endpoints:
  1. Validate input
  2. INSERT row with status="pending"
  3. Fire asyncio.create_task(run_extraction(...)) — does NOT await it
  4. Return 202 immediately with {id, status, message}

The client polls GET /knowledge/{id} (or uses a WebSocket in Stage 5)
to check when status transitions to "done" or "failed".
"""

import asyncio
import uuid
from typing import Annotated

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    Query, Request, UploadFile, status,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, AsyncSessionLocal  # your existing session dep + factory
from routers.auth import get_current_user
from models.knowledge import KnowledgeItem, CollectionItem, ContentType, ItemStatus
from models.user import User
from schemas.knowledge import (
    IngestAccepted,
    KnowledgeItemCreate,
    KnowledgeItemListOut,
    KnowledgeItemOut,
)
from services.extraction_task import run_extraction
from utils.content_type import detect_content_type  # see stub below

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Helper: fetch item owned by current user
# ---------------------------------------------------------------------------

async def _get_item_for_user(
    item_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> KnowledgeItem:
    result = await db.execute(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id,
            KnowledgeItem.user_id == user.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


# ---------------------------------------------------------------------------
# POST /knowledge — URL ingest
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestAccepted,
    summary="Ingest a URL",
)
async def ingest_url(
    payload: KnowledgeItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IngestAccepted:
    """
    Saves the URL immediately and returns 202.
    Extraction (fetch, parse, Gemini summary) runs as a background task.
    """
    content_type = detect_content_type(payload.url)

    item = KnowledgeItem(
        user_id=current_user.id,
        url=payload.url,
        content_type=content_type,
        tags=payload.tags,
        status=ItemStatus.PENDING.value,
        is_processed=False,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Add to collection if requested — do this before firing the task
    if payload.collection_id:
        await _add_to_collection(item.id, payload.collection_id, current_user.id, db)

    # Fire-and-forget: asyncio.create_task schedules on the running event loop.
    # AsyncSessionLocal is the session factory (not a session instance) so the
    # task creates its own fresh session — the request session above is closed
    # at end of this function.
    asyncio.create_task(
        run_extraction(item.id, AsyncSessionLocal),
        name=f"extract-{item.id}",
    )

    return IngestAccepted(id=item.id, status=item.status)


# ---------------------------------------------------------------------------
# POST /knowledge/upload-pdf — PDF ingest
# ---------------------------------------------------------------------------

@router.post(
    "/upload-pdf",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IngestAccepted,
    summary="Ingest a PDF file",
)
async def ingest_pdf(
    file: UploadFile = File(..., description="PDF file to ingest"),
    # Form fields for metadata — FastAPI reads these alongside the file
    tags: str | None = Form(None, description="Comma-separated tags"),
    title: str | None = Form(None, max_length=500),
    collection_id: uuid.UUID | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IngestAccepted:
    """
    Accepts a multipart/form-data upload.
    Saves the file to your storage backend, then returns 202.

    File size limit: enforce at the nginx/proxy layer (e.g. client_max_body_size 20m)
    rather than here — reading the entire file into memory to check size defeats
    the purpose of streaming uploads.
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are accepted",
        )

    # ── Save to storage ────────────────────────────────────────────────────
    # Replace with your actual storage call (S3, Cloudflare R2, Supabase Storage).
    # For local dev, write to /tmp and use a file:// URL.
    storage_url = await _save_pdf_to_storage(file, current_user.id)

    # Parse comma-separated tags from form field
    parsed_tags: list[str] | None = None
    if tags:
        parsed_tags = [t.strip().lower() for t in tags.split(",") if t.strip()] or None

    item = KnowledgeItem(
        user_id=current_user.id,
        url=storage_url,      # storage path — not a web URL, but reuses url column
        title=title,
        content_type=ContentType.PDF.value,
        tags=parsed_tags,
        status=ItemStatus.PENDING.value,
        is_processed=False,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    if collection_id:
        await _add_to_collection(item.id, collection_id, current_user.id, db)

    asyncio.create_task(
        run_extraction(item.id, AsyncSessionLocal),
        name=f"extract-pdf-{item.id}",
    )

    return IngestAccepted(id=item.id, status=item.status)


# ---------------------------------------------------------------------------
# GET /knowledge — list
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=list[KnowledgeItemListOut],
    summary="List knowledge items",
)
async def list_knowledge_items(
    content_type: ContentType | None = Query(None, description="Filter by content type"),
    status_filter: ItemStatus | None = Query(None, alias="status", description="Filter by processing status"),
    search: str | None = Query(None, min_length=1, max_length=200, description="Title contains (case-insensitive)"),
    # Simple pagination — offset-based is fine for this use case
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[KnowledgeItemListOut]:
    stmt = (
        select(KnowledgeItem)
        .where(KnowledgeItem.user_id == current_user.id)
    )

    if content_type is not None:
        stmt = stmt.where(KnowledgeItem.content_type == content_type.value)

    if status_filter is not None:
        stmt = stmt.where(KnowledgeItem.status == status_filter.value)

    if search:
        # ILIKE is case-insensitive pattern match. Per-user result sets are
        # small enough that this is fast without a full-text index at this scale.
        # Upgrade to to_tsvector GIN index when needed.
        stmt = stmt.where(KnowledgeItem.title.ilike(f"%{search}%"))

    stmt = (
        stmt
        .order_by(KnowledgeItem.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(stmt)
    items = result.scalars().all()
    return [KnowledgeItemListOut.model_validate(i) for i in items]


# ---------------------------------------------------------------------------
# GET /knowledge/{item_id} — single item with raw_text
# ---------------------------------------------------------------------------

@router.get(
    "/{item_id}",
    response_model=KnowledgeItemOut,
    summary="Get a single knowledge item",
)
async def get_knowledge_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeItemOut:
    item = await _get_item_for_user(item_id, current_user, db)
    return KnowledgeItemOut.model_validate(item)


# ---------------------------------------------------------------------------
# DELETE /knowledge/{item_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a knowledge item",
)
async def delete_knowledge_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Hard delete. CollectionItem rows cascade automatically via FK.
    If the item is mid-extraction, the background task will get a 404 when
    it tries to write back and log an error — this is acceptable. A running
    task cannot be cancelled without a task registry (add that in Stage 5).
    """
    item = await _get_item_for_user(item_id, current_user, db)
    await db.delete(item)
    await db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _add_to_collection(
    item_id: uuid.UUID,
    collection_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """
    Adds item to collection. Silently ignores if already present (upsert).
    Validates collection ownership to prevent cross-user collection pollution.
    """
    from models.knowledge import Collection  # local import avoids circular
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    # Verify the collection belongs to this user
    coll_result = await db.execute(
        select(Collection.id).where(
            Collection.id == collection_id,
            Collection.user_id == user_id,
        )
    )
    if coll_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found",
        )

    # ON CONFLICT DO NOTHING — the unique constraint handles duplicates cleanly
    stmt = pg_insert(CollectionItem).values(
        collection_id=collection_id,
        knowledge_item_id=item_id,
    ).on_conflict_do_nothing(
        constraint="uq_collection_item"
    )
    await db.execute(stmt)
    await db.commit()


async def _save_pdf_to_storage(file: UploadFile, user_id: uuid.UUID) -> str:
    """
    Stub — replace with your storage backend.

    Example for Supabase Storage:
        from supabase import create_client
        sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        path = f"pdfs/{user_id}/{uuid.uuid4()}.pdf"
        content = await file.read()
        sb.storage.from_("knowledge").upload(path, content)
        return sb.storage.from_("knowledge").get_public_url(path)

    Example for local dev:
        import aiofiles, pathlib
        dest = pathlib.Path(f"/tmp/flowdesk/{user_id}")
        dest.mkdir(parents=True, exist_ok=True)
        out_path = dest / f"{uuid.uuid4()}.pdf"
        async with aiofiles.open(out_path, "wb") as f:
            await f.write(await file.read())
        return str(out_path)
    """
    raise NotImplementedError("Implement _save_pdf_to_storage for your storage backend")


# ---------------------------------------------------------------------------
# utils/content_type.py — paste this into a separate file
# ---------------------------------------------------------------------------
# from urllib.parse import urlparse
#
# def detect_content_type(url: str) -> str:
#     hostname = urlparse(url).hostname or ""
#     if "youtube.com" in hostname or "youtu.be" in hostname:
#         return "youtube"
#     if "github.com" in hostname:
#         return "github"
#     if "twitter.com" in hostname or "x.com" in hostname:
#         return "twitter"
#     if "linkedin.com" in hostname:
#         return "linkedin"
#     return "article"  # default for all other URLs
