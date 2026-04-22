import json
import asyncio
from pywebpush import webpush, WebPushException
from core.config import settings
from models.notification import PushSubscription

# Robust import for the Vapid library (handles both 'vapid' and 'py_vapid' package names)
try:
    from vapid import Vapid
except ImportError:
    try:
        from py_vapid import Vapid
    except ImportError:
        Vapid = None

def _get_vapid_obj():
    """
    Returns a Vapid object loaded directly from the Base64URL private key string.
    """
    if Vapid is None:
        print("ERROR: Vapid library not found in environment")
        return None

    raw_key = (settings.VAPID_PRIVATE_KEY or "").strip().strip('"').strip("'")
    try:
        # Vapid.from_string is the standard way to load a base64url or PEM key
        return Vapid.from_string(raw_key.replace("\\n", "\n"))
    except Exception as e:
        print(f"ERROR: Could not load VAPID key: {e}")
        return None

async def send_push_notification(subscription: PushSubscription, title: str, body: str):
    """Sends a Web Push Notification using VAPID keys."""
    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        },
    }

    payload = json.dumps({"title": title, "body": body})

    try:
        vapid_obj = _get_vapid_obj()
        if not vapid_obj:
            return False

        await asyncio.to_thread(
            webpush,
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=vapid_obj,
            vapid_claims={"sub": f"mailto:{settings.VAPID_CLAIM_EMAIL}"},
        )
        return True
    except WebPushException as e:
        response_status = getattr(getattr(e, "response", None), "status_code", None)
        if response_status == 410 or "410" in str(e):
            return "EXPIRED"
        print(f"WebPush Exception for sub {subscription.id}: {e}")
        return False
    except Exception as e:
        print(f"Unknown Push Exception for sub {subscription.id}: {e}")
        return False