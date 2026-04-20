from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_
import uuid

from models.task import Task, TaskScope

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