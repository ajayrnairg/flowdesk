import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, UniqueConstraint
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

    # Clerk user ID — populated on first Clerk-authenticated request.
    # Nullable so existing rows (created before Clerk migration) are not broken.
    # Once set, it never changes — a Clerk identity maps 1:1 to a FlowDesk user.
    # String(255): Clerk IDs are currently ~32 chars (e.g. "user_2abc..."),
    # 255 is future-proof.
    clerk_user_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    # Alternative: explicit named constraint (easier to reference in migrations)
    __table_args__ = (
        UniqueConstraint("clerk_user_id", name="uq_users_clerk_user_id"),
    )
    # Then remove unique=True from the mapped_column above
    
    # Automatically capture the UTC timestamp on creation
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")
    notifications = relationship("NotificationLog", back_populates="user", cascade="all, delete-orphan")
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all, delete-orphan")
    knowledge_items = relationship("KnowledgeItem", back_populates="user", cascade="all, delete-orphan")