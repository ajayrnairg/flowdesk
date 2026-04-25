"""
routers/collections.py

Collections module for FlowDesk.

Route map:
  GET    /collections                         — list all collections w/ counts
  POST   /collections                         — create custom collection
  PATCH  /collections/{collection_id}         — rename / recolor
  DELETE /collections/{collection_id}         — delete (not items)
  GET    /collections/{collection_id}/items   — items in collection (filtered)
  POST   /collections/{collection_id}/items   — add item to collection
  DELETE /collections/{collection_id}/items/{item_id}  — remove item

  GET    /library                             — single-call Library page data

  PATCH  /knowledge/{item_id}/read-status     — update read progress
"""
import uuid
from typing import Optional
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, case

from core.database import get_db
from routers.auth import get_current_user
from models.user import User
from models.knowledge import Collection, CollectionItem, KnowledgeItem

from schemas.knowledge import (
    CollectionCreate, CollectionUpdate, CollectionOut,
    CollectionItemAdd, KnowledgeItemListOut, KnowledgeItemOut,
    LibraryResponse, LibraryCollectionEntry, LibraryItemPreview,
)

router = APIRouter(prefix="/collections", tags=["collections"])

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_collection_or_404(
    collection_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Collection:
    """Fetches a collection and strictly enforces user ownership."""
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await db.execute(stmt)
    coll = result.scalar_one_or_none()

    if not coll or coll.user_id != current_user.id:
        # Return 404 instead of 403 to prevent leaking the existence of other users' IDs
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    return coll

# ── Standard CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[CollectionOut])
async def list_collections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all collections with aggregated item and unread counts."""
    # Subquery: Count total items and unread items per collection
    counts_stmt = (
        select(
            CollectionItem.collection_id,
            func.count(CollectionItem.id).label("item_count"),
            func.sum(
                case((KnowledgeItem.read_status == "UNREAD", 1), else_=0)
            ).label("unread_count"),
        )
        .join(KnowledgeItem, KnowledgeItem.id == CollectionItem.knowledge_item_id)
        .group_by(CollectionItem.collection_id)
        .subquery()
    )

    stmt = (
        select(
            Collection,
            func.coalesce(counts_stmt.c.item_count, 0).label("item_count"),
            func.coalesce(counts_stmt.c.unread_count, 0).label("unread_count"),
        )
        .outerjoin(counts_stmt, counts_stmt.c.collection_id == Collection.id)
        .where(Collection.user_id == current_user.id)
        .order_by(Collection.is_default.desc(), Collection.created_at.asc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    collections = []
    for row in rows:
        coll = row[0]
        out = CollectionOut.model_validate(coll)
        out.item_count = row[1]
        out.unread_count = row[2]
        collections.append(out)

    return collections

@router.post("", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
async def create_collection(
    payload: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a custom user collection."""
    coll = Collection(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        emoji=payload.emoji,
        is_default=False,
    )
    db.add(coll)
    await db.commit()
    await db.refresh(coll)

    out = CollectionOut.model_validate(coll)
    return out

@router.patch("/{collection_id}", response_model=CollectionOut)
async def update_collection(
    collection_id: uuid.UUID,
    payload: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rename, recolor, or update the emoji of a collection."""
    coll = await _get_collection_or_404(collection_id, current_user, db)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(coll, field, value)

    await db.commit()
    await db.refresh(coll)
    return CollectionOut.model_validate(coll)

@router.get("/{collection_id}", response_model=CollectionOut)
async def get_collection(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a single collection by ID."""
    coll = await _get_collection_or_404(collection_id, current_user, db)
    return CollectionOut.model_validate(coll)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a collection. Rejects deletion if it's an auto-generated default."""
    coll = await _get_collection_or_404(collection_id, current_user, db)
    
    if coll.is_default:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Default collections cannot be deleted. Remove items instead."
        )

    await db.delete(coll)
    await db.commit()

# ── Items within Collections ──────────────────────────────────────────────────

@router.get("/{collection_id}/items", response_model=list[KnowledgeItemListOut])
async def list_collection_items(
    collection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists all knowledge items currently in a specific collection."""
    await _get_collection_or_404(collection_id, current_user, db)

    # Prioritize UNREAD items to the top, then sort chronologically
    read_order = case(
        (KnowledgeItem.read_status == "UNREAD", 0),
        (KnowledgeItem.read_status == "READING", 1),
        else_=2,
    )

    stmt = (
        select(KnowledgeItem)
        .join(CollectionItem, CollectionItem.knowledge_item_id == KnowledgeItem.id)
        .where(CollectionItem.collection_id == collection_id)
        .order_by(read_order, KnowledgeItem.created_at.desc())
    )

    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/{collection_id}/items", status_code=status.HTTP_201_CREATED)
async def add_item_to_collection(
    collection_id: uuid.UUID,
    payload: CollectionItemAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Links an existing KnowledgeItem to a Collection."""
    await _get_collection_or_404(collection_id, current_user, db)

    # Enforce item ownership
    item_stmt = select(KnowledgeItem).where(
        KnowledgeItem.id == payload.knowledge_item_id,
        KnowledgeItem.user_id == current_user.id,
    )
    if not (await db.execute(item_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge item not found")

    # Prevent duplicates
    exist_stmt = select(CollectionItem).where(
        CollectionItem.collection_id == collection_id,
        CollectionItem.knowledge_item_id == payload.knowledge_item_id,
    )
    if (await db.execute(exist_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item already in collection")

    ci = CollectionItem(collection_id=collection_id, knowledge_item_id=payload.knowledge_item_id)
    db.add(ci)
    await db.commit()
    return {"status": "added"}

@router.delete("/{collection_id}/items/{knowledge_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item_from_collection(
    collection_id: uuid.UUID,
    knowledge_item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removes a KnowledgeItem from a Collection (item is not deleted)."""
    await _get_collection_or_404(collection_id, current_user, db)

    stmt = select(CollectionItem).where(
        CollectionItem.collection_id == collection_id,
        CollectionItem.knowledge_item_id == knowledge_item_id,
    )
    ci = (await db.execute(stmt)).scalar_one_or_none()

    if not ci:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not in collection")

    await db.delete(ci)
    await db.commit()

# ── Library View (Aggregated) ─────────────────────────────────────────────────

@router.get("/library/overview", response_model=LibraryResponse)
async def get_library(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Performance-critical endpoint: Renders the entire Library page.
    Optimization: Loads ALL required data in exactly 2 DB queries using an IN clause
    and Python-side grouping, preventing the N+1 problem completely.
    """
    # ── Query 1: Fetch all collections and their aggregated counts
    counts_sub = (
        select(
            CollectionItem.collection_id,
            func.count(CollectionItem.id).label("item_count"),
            func.sum(case((KnowledgeItem.read_status == "UNREAD", 1), else_=0)).label("unread_count"),
        )
        .join(KnowledgeItem, KnowledgeItem.id == CollectionItem.knowledge_item_id)
        .group_by(CollectionItem.collection_id)
        .subquery()
    )

    coll_stmt = (
        select(
            Collection,
            func.coalesce(counts_sub.c.item_count, 0).label("item_count"),
            func.coalesce(counts_sub.c.unread_count, 0).label("unread_count"),
        )
        .outerjoin(counts_sub, counts_sub.c.collection_id == Collection.id)
        .where(Collection.user_id == current_user.id)
        .order_by(Collection.is_default.desc(), Collection.created_at.asc())
    )

    coll_rows = (await db.execute(coll_stmt)).all()
    if not coll_rows:
        return LibraryResponse(collections=[], total_items=0, total_unread=0)

    collection_ids = [row[0].id for row in coll_rows]

    # ── Query 2: Fetch ALL items belonging to those collections using IN clause
    items_stmt = (
        select(CollectionItem.collection_id, KnowledgeItem)
        .join(KnowledgeItem, KnowledgeItem.id == CollectionItem.knowledge_item_id)
        .where(CollectionItem.collection_id.in_(collection_ids))
        .order_by(
            case((KnowledgeItem.read_status == "UNREAD", 0), else_=1),
            KnowledgeItem.created_at.desc()
        )
    )
    item_rows = (await db.execute(items_stmt)).all()

    # ── Python Assembly: Group by collection ID
    grouped_items = defaultdict(list)
    for coll_id, item in item_rows:
        # We only want the first 10 items for the UI shelf preview
        if len(grouped_items[coll_id]) < 10:
            grouped_items[coll_id].append(LibraryItemPreview.model_validate(item))

    # ── Final Composition
    total_items = 0
    total_unread = 0
    entries = []

    for row in coll_rows:
        coll, item_count, unread_count = row[0], int(row[1]), int(row[2])
        total_items += item_count
        total_unread += unread_count

        entries.append(
            LibraryCollectionEntry(
                id=coll.id,
                name=coll.name,
                description=coll.description,
                color=coll.color,
                emoji=coll.emoji,
                is_default=coll.is_default,
                item_count=item_count,
                unread_count=unread_count,
                items=grouped_items.get(coll.id, []),
            )
        )

    return LibraryResponse(
        collections=entries,
        total_items=total_items,
        total_unread=total_unread,
    )