from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID

from core.database import get_db
from routers.auth import get_current_user
from models.user import User
from models.task import Task, TaskScope, TaskPriority
from schemas.task import TaskCreate, TaskUpdate, TaskToggle, TaskOut

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all tasks for the current user.
    Ordered by: Incomplete first -> High priority first -> Due date earliest first.
    """
    # 1. Base query constrained strictly to the current user
    stmt = select(Task).where(Task.user_id == current_user.id)
    
    # 2. Apply optional filters
    if scope:
        stmt = stmt.where(Task.scope == scope)
    if is_done is not None:
        stmt = stmt.where(Task.is_done == is_done)
        
    # 3. Apply complex ordering
    # - is_done.asc(): False (0) comes before True (1), so undone tasks appear first.
    # - priority.desc(): Postgres Enum uses creation order (LOW, MEDIUM, HIGH). 
    #   Descending makes HIGH appear first.
    # - due_date.asc().nulls_last(): Earliest due dates first; tasks without due dates go to the bottom.
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
    """Creates a new task associated with the current user."""
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
    
    # exclude_unset=True ensures we only touch fields the client explicitly sent
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