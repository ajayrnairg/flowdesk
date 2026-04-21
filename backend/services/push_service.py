import json
import asyncio
from pywebpush import webpush, WebPushException
from core.config import settings
from models.notification import PushSubscription
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

def _get_private_key():
    """
    Load the private key. Supports:
    1. Raw 32-byte hex string (Recommended for Render)
    2. PEM formatted string
    """
    key_str = settings.VAPID_PRIVATE_KEY.strip().strip('"').strip("'")
    
    # If it's hex (64 chars), load it directly as a 32-byte integer
    if len(key_str) == 64:
        try:
            d = int(key_str, 16)
            return ec.derive_private_key(d, ec.SECP256R1()).private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        except ValueError:
            pass

    # Fallback: assume it's PEM (or handle literal \n)
    return key_str.replace("\\n", "\n")

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
        await asyncio.to_thread(
            webpush,
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=_get_private_key(),
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