import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_

from core.database import get_db, AsyncSessionLocal
from routers.auth import get_current_user
from models.user import User
from models.knowledge import KnowledgeItem, CollectionItem, ItemStatus
from schemas.knowledge import KnowledgeItemCreate, KnowledgeItemOut, IngestAccepted
from schemas.knowledge_extra import BookmarkletPayload # Imported from the schema above

from services.content_detector import detect_content_type
from services.pdf_extractor import extract_pdf_text
from services.ingestion_orchestrator import run_ingestion_pipeline, run_summary_only

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

async def _get_item_or_404(item_id: uuid.UUID, current_user: User, db: AsyncSession) -> KnowledgeItem:
    """Helper to fetch an item and enforce strict ownership."""
    stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found")
    if item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this item")
        
    return item

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def ingest_url(
    payload: KnowledgeItemCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ingests a standard URL. Defers heavy extraction to a background task."""
    content_type = detect_content_type(payload.url)
    
    # Fast-fail for platforms that block standard scraping
    if content_type in ["twitter", "linkedin"]:
        return {
            "status": "use_bookmarklet", 
            "message": f"Use the bookmarklet to save {content_type.capitalize()} content securely."
        }
        
    new_item = KnowledgeItem(
        user_id=current_user.id,
        url=payload.url,
        content_type=content_type,
        tags=payload.tags,
        status=ItemStatus.PENDING.value,
        is_processed=False
    )
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)
    
    # Handle optional collection grouping
    if payload.collection_id:
        coll_item = CollectionItem(
            collection_id=payload.collection_id,
            knowledge_item_id=new_item.id
        )
        db.add(coll_item)
        await db.commit()

    # NOTE ON DB SESSIONS IN BACKGROUND TASKS: 
    # FastAPI Depends(get_db) closes the session immediately after the HTTP response returns.
    # Passing `db` directly into a BackgroundTask often causes "DetachedInstanceError". 
    # To be perfectly safe, it is best practice to pass a new session from your sessionmaker.
    async def safe_ingestion_runner(item_id: uuid.UUID):
        async with AsyncSessionLocal() as bg_db:
            await run_ingestion_pipeline(item_id, bg_db)

    background_tasks.add_task(safe_ingestion_runner, new_item.id)
    
    return IngestAccepted(id=new_item.id, status=new_item.status)

@router.post("/bookmarklet", status_code=status.HTTP_202_ACCEPTED)
async def ingest_bookmarklet(
    payload: BookmarkletPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ingests highlighted text sent directly from the browser bookmarklet."""
    new_item = KnowledgeItem(
        user_id=current_user.id,
        url=payload.url,
        title=payload.page_title,
        raw_text=payload.selected_text,
        content_type=payload.content_type,
        status=ItemStatus.PROCESSING.value,
        is_processed=False
    )
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)

    if payload.collection_id:
        coll_item = CollectionItem(collection_id=payload.collection_id, knowledge_item_id=new_item.id)
        db.add(coll_item)
        await db.commit()

    # Background task only needs to generate the Gemini summary now
    async def safe_summary_runner(item_id: uuid.UUID):
        async with AsyncSessionLocal() as bg_db:
            await run_summary_only(item_id, bg_db)

    background_tasks.add_task(safe_summary_runner, new_item.id)
    
    return {"status": "accepted", "id": new_item.id}

@router.post("/upload-pdf", status_code=status.HTTP_202_ACCEPTED)
async def ingest_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Synchronously extracts PDF text (fast), async generates summary (slow)."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="File must be a PDF")
        
    file_bytes = await file.read()
    
    # Run the PDF extractor (it uses asyncio.to_thread internally to prevent blocking)
    ext_result = await extract_pdf_text(file_bytes, file.filename)
    
    if ext_result.get("error") == "file_too_large":
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="PDF exceeds 10MB limit")
    elif "error" in ext_result:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=ext_result["error"])

    new_item = KnowledgeItem(
        user_id=current_user.id,
        content_type="pdf",
        title=ext_result.get("title"),
        raw_text=ext_result.get("raw_text"),
        status=ItemStatus.PROCESSING.value,
        is_processed=False
    )
    db.add(new_item)
    await db.commit()
    await db.refresh(new_item)

    async def safe_summary_runner(item_id: uuid.UUID):
        async with AsyncSessionLocal() as bg_db:
            await run_summary_only(item_id, bg_db)

    background_tasks.add_task(safe_summary_runner, new_item.id)
    
    return {"status": "accepted", "id": new_item.id}

@router.get("", response_model=List[KnowledgeItemOut])
async def list_knowledge(
    content_type: Optional[str] = None,
    item_status: Optional[str] = None, # Renamed to avoid shadowing 'status' module
    q: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns a filtered, ordered list of the user's knowledge items."""
    stmt = select(KnowledgeItem).where(KnowledgeItem.user_id == current_user.id)
    
    if content_type:
        stmt = stmt.where(KnowledgeItem.content_type == content_type)
    if item_status:
        stmt = stmt.where(KnowledgeItem.status == item_status)
    if q:
        # Case-insensitive ilike search on the title
        stmt = stmt.where(KnowledgeItem.title.ilike(f"%{q}%"))
        
    stmt = stmt.order_by(KnowledgeItem.created_at.desc())
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/{item_id}", response_model=KnowledgeItemOut)
async def get_knowledge_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full details of a specific knowledge item."""
    return await _get_item_or_404(item_id, current_user, db)

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Hard deletes a knowledge item. M2M CollectionItem joins cascade automatically."""
    item = await _get_item_or_404(item_id, current_user, db)
    await db.delete(item)
    await db.commit()