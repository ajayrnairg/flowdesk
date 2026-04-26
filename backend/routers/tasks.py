import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlalchemy.future import select
from uuid import UUID

from core.database import get_db
from core.clerk_auth import get_current_user
from models.user import User
from models.task import Task, TaskScope, TaskPriority
from schemas.task import TaskCreate, TaskUpdate, TaskToggle, TaskOut

logger = logging.getLogger("flowdesk.tasks")

router = APIRouter(prefix="/tasks", tags=["tasks"])

async def get_task_or_fail(task_id: UUID, current_user: User, db: AsyncSession) -> Task:
    """
    Helper dependency to fetch a task and enforce strict ownership rules.
    Returns 404 if it doesn't exist, and 403 if the user doesn't own it.
    """
    stmt = select(Task).where(Task.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        
    if task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You do not have permission to access this task"
        )
        
    return task

@router.get("", response_model=list[TaskOut])
async def list_tasks(
    scope: TaskScope | None = Query(None, description="Filter by task scope"),
    is_done: bool | None = Query(None, description="Filter by completion status"),
    is_history: bool = Query(False, description="Whether to return historical completed tasks"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all tasks for the current user.
    Spawns new instances for recurring tasks if they don't exist for today.
    Ordered by: Incomplete first -> High priority first -> Due date earliest first.
    """
    from datetime import date
    today = date.today()

    # 1. Recurring task spawning logic
    master_stmt = select(Task).where(
        Task.user_id == current_user.id,
        Task.is_recurring == True
    )
    if scope:
        master_stmt = master_stmt.where(Task.scope == scope)
    
    master_res = await db.execute(master_stmt)
    masters = master_res.scalars().all()

    for master in masters:
        # Prevent re-spawning if already spawned today (even if the instance was deleted)
        if master.last_spawned_at == today:
            continue

        # Double check if an instance exists (in case last_spawned_at wasn't set)
        instance_stmt = select(Task).where(
            Task.parent_id == master.id,
            Task.due_date == today
        )
        instance_res = await db.execute(instance_stmt)
        if not instance_res.scalar_one_or_none():
            # Create a fresh instance for today
            new_instance = Task(
                user_id=current_user.id,
                title=master.title,
                notes=master.notes,
                scope=master.scope,
                priority=master.priority,
                due_date=today,
                parent_id=master.id,
                is_recurring=False
            )
            db.add(new_instance)
            # Update master to mark that it spawned today
            master.last_spawned_at = today
    
    await db.commit()

    # 2. Main query to return tasks for the UI
    if is_history:
        stmt = select(Task).where(
            Task.user_id == current_user.id,
            Task.is_done == True,
            Task.is_recurring == False
        ).order_by(Task.updated_at.desc())
        
        if scope:
            stmt = stmt.where(Task.scope == scope)
    else:
        stmt = select(Task).where(
            Task.user_id == current_user.id,
            Task.is_recurring == False
        )
        
        if scope:
            stmt = stmt.where(Task.scope == scope)
            if scope == TaskScope.DAILY:
                stmt = stmt.where(
                    (Task.is_done == False) | (Task.due_date == today)
                )
    
        if is_done is not None:
            stmt = stmt.where(Task.is_done == is_done)
            
        stmt = stmt.order_by(
            Task.is_done.asc(),
            Task.priority.desc(),
            Task.due_date.asc().nulls_last()
        )
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a new task. Prevents duplicates for the same user."""
    # Check for existing task with same title (case-insensitive)
    existing_stmt = select(Task).where(
        Task.user_id == current_user.id,
        func.lower(Task.title) == func.lower(payload.title)
    )
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A task with the title '{payload.title}' already exists."
        )

    new_task = Task(
        user_id=current_user.id,
        **payload.model_dump()
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task

@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partially updates a task's title, notes, priority, or due_date."""
    task = await get_task_or_fail(task_id, current_user, db)
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
        
    await db.commit()
    await db.refresh(task)
    return task

@router.patch("/{task_id}/toggle", response_model=TaskOut)
async def toggle_task_status(
    task_id: UUID,
    payload: TaskToggle,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly toggles the completion status of a task."""
    task = await get_task_or_fail(task_id, current_user, db)
    
    task.is_done = payload.is_done
    if payload.is_done:
        from datetime import date
        task.last_completed_at = date.today()
        
    await db.commit()
    await db.refresh(task)
    return task

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hard deletes a task."""
    task = await get_task_or_fail(task_id, current_user, db)
    
    await db.delete(task)
    await db.commit()