import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from core.database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    # Use UUID4 for primary key, stored natively as UUID in Postgres
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    
    # Default timezone set to IST as requested
    timezone: Mapped[str] = mapped_column(String, default="Asia/Kolkata", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Automatically capture the UTC timestamp on creation
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")
    notifications = relationship("NotificationLog", back_populates="user", cascade="all, delete-orphan")
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")