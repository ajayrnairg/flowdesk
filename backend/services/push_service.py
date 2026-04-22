import json
import asyncio
import base64
from pywebpush import webpush, WebPushException
from core.config import settings
from models.notification import PushSubscription
from vapid import Vapid

def _get_vapid_obj():
    """
    Returns a Vapid object loaded from the private key.
    Handles:
    1. Raw 32-byte hex string
    2. Base64url encoded private key
    3. PEM string
    """
    raw_key = (settings.VAPID_PRIVATE_KEY or "").strip().strip('"').strip("'")
    
    # Create Vapid instance
    vapid_obj = Vapid()
    
    # 1. Try loading as raw 32-byte hex (64 chars)
    if len(raw_key) == 64:
        try:
            # Vapid.from_raw expects 32 bytes of binary data
            raw_bytes = bytes.fromhex(raw_key)
            return Vapid.from_raw(raw_bytes)
        except Exception as e:
            print(f"DEBUG: Vapid hex load failed: {e}")

    # 2. Try loading as base64url or PEM using the library's built-in loader
    try:
        # from_string handles PEM and base64url automatically
        return Vapid.from_string(raw_key.replace("\\n", "\n"))
    except Exception as e:
        print(f"DEBUG: Vapid string load failed: {e}")
        
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
            print(f"ERROR: Could not load VAPID key for sub {subscription.id}")
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