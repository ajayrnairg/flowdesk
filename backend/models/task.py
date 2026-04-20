import enum
import uuid
from datetime import datetime, date, timezone
from sqlalchemy import String, Boolean, Date, Text, Enum, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import expression, func
from core.database import Base

class TaskScope(str, enum.Enum):
    """Temporal planning horizon for a task."""
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"

class TaskPriority(str, enum.Enum):
    """Urgency/importance level."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_user_id_scope", "user_id", "scope"),
        Index("ix_tasks_user_id_is_done", "user_id", "is_done"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    
    # Ownership: cascades on delete so if a user is deleted, their tasks go too.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stored as native enums in Postgres for data integrity
    scope: Mapped[TaskScope] = mapped_column(
    Enum(TaskScope, name="task_scope", native_enum=False), nullable=False
    )
    priority: Mapped[TaskPriority] = mapped_column(
    Enum(TaskPriority, name="task_priority", native_enum=False),
    nullable=False,
    default=TaskPriority.MEDIUM,
    )

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=expression.false()
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    
    # Using onupdate allows SQLAlchemy to automatically bump this timestamp on ORM updates
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationship to user
    owner = relationship("User", back_populates="tasks", lazy="raise")