from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import date, datetime
from models.task import TaskScope, TaskPriority

# Base properties shared across schemas
class TaskBase(BaseModel):
    title: str = Field(..., max_length=255)
    notes: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    model_config = ConfigDict(use_enum_values=True)

# Used for POST /tasks
class TaskCreate(TaskBase):
    scope: TaskScope

# Used for PATCH /tasks/{task_id} - all fields optional
class TaskUpdate(BaseModel):
    title: str | None = Field(None, max_length=255)
    notes: str | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    model_config = ConfigDict(use_enum_values=True)

# Used for PATCH /tasks/{task_id}/toggle
class TaskToggle(BaseModel):
    is_done: bool

# Used for returning Task data (GET, POST responses)
class TaskOut(TaskBase):
    id: UUID
    user_id: UUID
    scope: TaskScope
    is_done: bool
    created_at: datetime
    updated_at: datetime

    # Pydantic v2 ORM mode equivalent
    model_config = ConfigDict(from_attributes=True)