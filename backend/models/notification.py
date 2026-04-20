import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from core.database import Base


class NotificationLog(Base):
    """Records every notification attempt sent to a user."""
    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # e.g. "morning_digest", "task_reminder"
    digest_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # e.g. "email", "push"
    channel: Mapped[str] = mapped_column(String(20), nullable=False)

    # e.g. "sent", "failed", "skipped"
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Optional detail: error message or push response body
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationship back to user
    user = relationship("User", back_populates="notifications")


class PushSubscription(Base):
    """Stores a browser's Web Push subscription for VAPID delivery."""
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        # One row per endpoint globally — the unique constraint requirement
        UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The full push service URL from the browser
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # VAPID encryption keys from the browser's PushSubscription.toJSON()
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional: helps debug which browser/device this is from
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationship back to user
    user = relationship("User", back_populates="push_subscriptions")
