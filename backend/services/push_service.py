import json
import asyncio
import base64
import textwrap
from pywebpush import webpush, WebPushException
from core.config import settings
from models.notification import PushSubscription

def _ensure_pem(key: str) -> str:
    """Return a PEM‑formatted EC private key.
    If the key already contains PEM headers we return it unchanged.
    Otherwise we assume the key is a URL‑safe base64 string (no padding)
    and wrap it in the standard PEM envelope.
    """
    if "BEGIN" in key:
        return key
    padded = key + "=" * ((4 - len(key) % 4) % 4)
    raw_bytes = base64.urlsafe_b64decode(padded)
    b64 = base64.b64encode(raw_bytes).decode()
    pem_body = "\n".join(textwrap.wrap(b64, 64))
    return f"-----BEGIN PRIVATE KEY-----\n{pem_body}\n-----END PRIVATE KEY-----"

async def send_push_notification(subscription: PushSubscription, title: str, body: str):
    """Sends a Web Push Notification using VAPID keys.
    Returns:
        True: Success
        False: Generic Failure
        "EXPIRED": sentinel for 410 Gone (subscription no longer valid)
    """
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
            vapid_private_key=_ensure_pem(settings.VAPID_PRIVATE_KEY),
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