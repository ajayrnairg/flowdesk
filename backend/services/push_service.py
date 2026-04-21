import json
import asyncio
from pywebpush import webpush, WebPushException
from core.config import settings
from models.notification import PushSubscription

async def send_push_notification(subscription: PushSubscription, title: str, body: str):
    """
    Sends a Web Push Notification using VAPID keys.
    Returns:
       True: Success
       False: Generic Failure
       "EXPIRED": Sentinel value indicating a 410 Gone response
    """
    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth
        }
    }
    
    payload = json.dumps({
        "title": title,
        "body": body
    })

    try:
        # pywebpush is synchronous; wrapping in to_thread prevents blocking the async event loop
        await asyncio.to_thread(
            webpush,
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIM_EMAIL}"}
        )
        return True
    except WebPushException as e:
        if e.response and e.response.status_code == 410:
            # 410 Gone means the user revoked permissions or the browser deleted the sub
            return "EXPIRED"
        print(f"WebPush Exception for sub {subscription.id}: {e}")
        return False
    except Exception as e:
        print(f"Unknown Push Exception for sub {subscription.id}: {e}")
        return False