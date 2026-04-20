import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from core.database import get_db
from core.config import settings
from routers.auth import get_current_user
from models.user import User
from models.notification import NotificationLog, PushSubscription
from schemas.notification import PushSubscriptionCreate
from services.digest_orchestrator import send_morning_digest_to_all_users

router = APIRouter(prefix="/notifications", tags=["notifications"])

def verify_token(token: str):
    """Helper dependency to verify server-to-server webhook tokens."""
    if token != settings.NOTIFICATION_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

@router.get("/check-and-send")
async def check_and_send_digest(token: str, db: AsyncSession = Depends(get_db)):
    """
    Time-gated UptimeRobot webhook. Checks if we are in the correct time window
    and if a digest was already sent today before triggering.
    """
    verify_token(token)
    
    now_utc = datetime.now(timezone.utc)
    
    # Time gating
    if now_utc.hour != settings.DIGEST_HOUR_UTC or now_utc.minute >= settings.DIGEST_WINDOW_MINUTES:
        return {"status": "outside_window"}
        
    # Deduplication logic: Convert current time to IST and create UTC bounds for today's IST date
    ist = ZoneInfo("Asia/Kolkata")
    ist_now = datetime.now(ist)
    
    # Start of today (IST), converted back to UTC for the database query
    ist_start_of_day = datetime(ist_now.year, ist_now.month, ist_now.day, tzinfo=ist)
    utc_bound_start = ist_start_of_day.astimezone(timezone.utc)
    utc_bound_end = utc_bound_start + timedelta(days=1)
    
    # Check if ANY digest was successfully sent today
    stmt = select(NotificationLog).where(
        NotificationLog.digest_type == "morning_digest",
        NotificationLog.status == "sent",
        NotificationLog.sent_at >= utc_bound_start,
        NotificationLog.sent_at < utc_bound_end
    ).limit(1)
    
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        return {"status": "already_sent"}
        
    # If we made it here, fire the orchestrator
    notified_count = await send_morning_digest_to_all_users(db)
    return {"status": "sent", "count": notified_count}

@router.post("/send-digest")
async def force_send_digest(token: str, db: AsyncSession = Depends(get_db)):
    """Unconditional trigger for GitHub actions / manual overrides."""
    verify_token(token)
    try:
        notified_count = await send_morning_digest_to_all_users(db)
        return {"status": "sent", "count": notified_count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/subscriptions", status_code=status.HTTP_201_CREATED)
async def create_subscription(
    payload: PushSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Saves or updates a browser VAPID push subscription."""
    # Check for existing endpoint to do an upsert
    stmt = select(PushSubscription).where(
        PushSubscription.endpoint == payload.endpoint, 
        PushSubscription.user_id == current_user.id
    )
    result = await db.execute(stmt)
    existing_sub = result.scalar_one_or_none()
    
    if existing_sub:
        existing_sub.p256dh = payload.keys.p256dh
        existing_sub.auth = payload.keys.auth
        existing_sub.user_agent = payload.user_agent
    else:
        new_sub = PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=payload.user_agent
        )
        db.add(new_sub)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="Endpoint registered to another account"
        )
        
    return {"detail": "Subscription saved"}

@router.delete("/subscriptions/{sub_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    sub_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Removes a subscription (e.g. user manually signs out of a device)."""
    stmt = select(PushSubscription).where(
        PushSubscription.id == sub_id,
        PushSubscription.user_id == current_user.id # strict ownership check
    )
    result = await db.execute(stmt)
    sub = result.scalar_one_or_none()
    
    if not sub:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized or not found")
        
    await db.delete(sub)
    await db.commit()