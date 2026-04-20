from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.user import User
from models.notification import NotificationLog, PushSubscription
from services.digest_query import build_digest_for_user
from services.email_service import send_digest_email
from services.push_service import send_push_notification

async def send_morning_digest_to_all_users(db: AsyncSession) -> int:
    """
    The master orchestrator. Iterates users, generates digests, sends notifications,
    and handles logging and cleanup without crashing on individual failures.
    """
    stmt = select(User).where(User.is_active == True)
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    users_notified = 0

    for user in users:
        # 1. Build Digest
        digest_data = await build_digest_for_user(user.id, db)
        
        # 2. Skip if totally empty
        if not any(digest_data.values()):
            continue
            
        users_notified += 1
        
        # 3. Send Email
        email_success = await send_digest_email(user, digest_data)
        
        # Log Email Attempt
        db.add(NotificationLog(
            user_id=user.id,
            digest_type="morning_digest",
            channel="email",
            status="sent" if email_success else "failed"
        ))
        
        # 4. Handle Push Notifications
        total_tasks = sum(len(tasks) for tasks in digest_data.values())
        push_title = "FlowDesk Morning Digest"
        push_body = f"You have {total_tasks} tasks on your radar today."
        
        sub_stmt = select(PushSubscription).where(PushSubscription.user_id == user.id)
        sub_result = await db.execute(sub_stmt)
        subscriptions = sub_result.scalars().all()
        
        for sub in subscriptions:
            push_result = await send_push_notification(sub, push_title, push_body)
            
            if push_result == "EXPIRED":
                # Clean up dead subscriptions immediately
                await db.delete(sub)
            else:
                # Log Push Attempt
                db.add(NotificationLog(
                    user_id=user.id,
                    digest_type="morning_digest",
                    channel="push",
                    status="sent" if push_result is True else "failed"
                ))
        
        # Commit logs and potential deletions per user to ensure data is saved
        # even if the orchestrator crashes on the next user
        await db.commit()

    return users_notified