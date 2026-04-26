from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, func
import uuid

from models.task import Task, TaskScope
from models.knowledge import KnowledgeItem, Collection, CollectionItem, ItemStatus, ReadStatus

async def build_digest_for_user(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """
    Fetches and buckets all undone tasks for a user.
    Uses IST to determine what "today", "this week", and "this month" mean.
    """
    # 1. Establish the current date in IST
    ist = ZoneInfo("Asia/Kolkata")
    today_ist = datetime.now(ist).date()
    
    # Calculate boundaries
    # Monday = 0, Sunday = 6
    week_start = today_ist - timedelta(days=today_ist.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Month boundaries
    month_start = today_ist.replace(day=1)
    # Next month minus one day gives the last day of the current month
    next_month = month_start.replace(month=month_start.month % 12 + 1, day=1)
    if month_start.month == 12:
        next_month = next_month.replace(year=month_start.year + 1)
    month_end = next_month - timedelta(days=1)

    # Base query: Only undone tasks for this specific user
    stmt = select(Task).where(Task.user_id == user_id, Task.is_done == False)
    result = await db.execute(stmt)
    all_undone_tasks = result.scalars().all()

    # Initialize buckets
    digest = {
        "daily_tasks": [],
        "weekly_tasks": [],
        "monthly_tasks": [],
        "overdue_tasks": []
    }

    # 2. Bucket the tasks
    for task in all_undone_tasks:
        # OVERDUE: Any task (except Daily) where due_date is entirely in the past
        if task.due_date and task.due_date < today_ist and task.scope != TaskScope.DAILY:
            digest["overdue_tasks"].append(task)
            continue # If it's overdue, it goes here and nowhere else

        # DAILY: Scope is daily (due_date is essentially ignored, it's a daily habit)
        if task.scope == TaskScope.DAILY:
            digest["daily_tasks"].append(task)
            
        # WEEKLY: Scope is weekly and due date is within this ISO week
        elif task.scope == TaskScope.WEEKLY and task.due_date:
            if week_start <= task.due_date <= week_end:
                digest["weekly_tasks"].append(task)
                
        # MONTHLY: Scope is monthly and due date is within this month
        elif task.scope == TaskScope.MONTHLY and task.due_date:
            if month_start <= task.due_date <= month_end:
                digest["monthly_tasks"].append(task)

    return digest

async def get_suggested_reading(user_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """
    Fetches up to 5 suggested reading items.
    1. If any items are marked 'is_priority', it returns those first.
    2. Otherwise, it picks at most ONE oldest unread item per collection.
    """
    # 1. Priority Check
    priority_stmt = (
        select(
            KnowledgeItem.title,
            KnowledgeItem.summary,
            KnowledgeItem.url,
            KnowledgeItem.content_type,
            KnowledgeItem.estimated_read_minutes,
            Collection.name.label("collection_name"),
            Collection.color.label("collection_color")
        )
        .outerjoin(CollectionItem, CollectionItem.knowledge_item_id == KnowledgeItem.id)
        .outerjoin(Collection, Collection.id == CollectionItem.collection_id)
        .where(
            KnowledgeItem.user_id == user_id,
            KnowledgeItem.is_priority == True,
            KnowledgeItem.status == ItemStatus.DONE.value,
            KnowledgeItem.read_status != ReadStatus.DONE.value
        )
        .order_by(KnowledgeItem.created_at.desc())
        .limit(5)
    )
    
    priority_res = await db.execute(priority_stmt)
    priority_rows = priority_res.all()
    
    if priority_rows:
        return [{
            "collection_name": row.collection_name or "Priority",
            "collection_color": row.collection_color or "#ef4444", # Red for priority
            "title": row.title,
            "summary": row.summary,
            "url": row.url,
            "content_type": row.content_type,
            "estimated_read_minutes": row.estimated_read_minutes
        } for row in priority_rows]

    # 2. Existing Collection-based Logic
    subq = (
        select(
            KnowledgeItem.id,
            KnowledgeItem.title,
            KnowledgeItem.summary,
            KnowledgeItem.url,
            KnowledgeItem.content_type,
            KnowledgeItem.estimated_read_minutes,
            CollectionItem.collection_id,
            func.row_number().over(
                partition_by=CollectionItem.collection_id,
                order_by=KnowledgeItem.created_at.asc()
            ).label("rn")
        )
        .join(CollectionItem, CollectionItem.knowledge_item_id == KnowledgeItem.id)
        .where(
            KnowledgeItem.user_id == user_id,
            KnowledgeItem.status == ItemStatus.DONE.value,
            KnowledgeItem.read_status == ReadStatus.UNREAD.value
        )
        .subquery()
    )

    stmt = (
        select(
            Collection.name.label("collection_name"),
            Collection.color.label("collection_color"),
            subq.c.title,
            subq.c.summary,
            subq.c.url,
            subq.c.content_type,
            subq.c.estimated_read_minutes
        )
        .join(Collection, Collection.id == subq.c.collection_id)
        .where(subq.c.rn == 1)
        .limit(5)
    )

    result = await db.execute(stmt)
    rows = result.all()

    suggestions = []
    for row in rows:
        suggestions.append({
            "collection_name": row.collection_name,
            "collection_color": row.collection_color,
            "title": row.title,
            "summary": row.summary,
            "url": row.url,
            "content_type": row.content_type,
            "estimated_read_minutes": row.estimated_read_minutes
        })

    return suggestions