import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.user import User
from models.notification import NotificationLog, PushSubscription
from services.digest_query import build_digest_for_user, get_suggested_reading
from services.email_service import send_digest_email
from services.push_service import send_push_notification

logger = logging.getLogger(__name__)

async def send_digest_to_user(user: User, db: AsyncSession) -> bool:
    """
    Orchestrates the digest for a single user: builds data, sends email, sends push.
    Returns True if something was sent (or attempted), False if no content was found.
    """
    # 1. Build Digest
    digest_data = await build_digest_for_user(user.id, db)
    
    try:
        suggested_reading = await get_suggested_reading(user.id, db)
    except Exception as e:
        logger.error(f"Failed to get suggested reading for {user.id}: {e}")
        suggested_reading = []
    
    # 2. Skip if totally empty
    if not any(digest_data.values()) and not suggested_reading:
        return False
        
    # 3. Send Email
    email_success = await send_digest_email(user, digest_data, suggested_reading)
    
    db.add(NotificationLog(
        user_id=user.id,
        digest_type="morning_digest",
        channel="email",
        status="sent" if email_success else "failed"
    ))
    
    # 4. Handle Push Notifications
    total_tasks = sum(len(tasks) for tasks in digest_data.values())
    push_title = "FlowDesk Morning Digest"
    push_body = (
        f"You have {total_tasks} tasks on your radar today." 
        if total_tasks > 0 else 
        f"You have {len(suggested_reading)} items in your reading backlog."
    )
        
    sub_stmt = select(PushSubscription).where(PushSubscription.user_id == user.id)
    sub_result = await db.execute(sub_stmt)
    subscriptions = sub_result.scalars().all()
    
    for sub in subscriptions:
        push_result = await send_push_notification(sub, push_title, push_body)
        if push_result == "EXPIRED":
            await db.delete(sub)
        else:
            db.add(NotificationLog(
                user_id=user.id,
                digest_type="morning_digest",
                channel="push",
                status="sent" if push_result is True else "failed"
            ))
    
    await db.commit()
    return True

async def send_morning_digest_to_all_users(db: AsyncSession) -> int:
    """Iterates all active users and sends digests."""
    stmt = select(User).where(User.is_active == True)
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    users_notified = 0
    for user in users:
        sent = await send_digest_to_user(user, db)
        if sent:
            users_notified += 1
            
    return users_notified