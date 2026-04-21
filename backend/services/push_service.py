import json
import asyncio
import base64
import textwrap
from pywebpush import webpush, WebPushException
from core.config import settings
from models.notification import PushSubscription

def _ensure_pem(key: str) -> str:
    """
    Return a PEM-formatted EC private key.
    Handles raw base64, base64url, and existing PEM strings.
    """
    # 1. Clean up the input
    key = key.strip().strip('"').strip("'")
    # Handle literal \n sequences often found in env vars
    key = key.replace("\\n", "\n")
    
    # 2. If it's already PEM, return as is
    if "-----BEGIN" in key:
        return key
        
    # 3. Convert from base64/base64url to standard bytes
    # Replace URL-safe characters just in case, then add padding
    key_clean = key.replace("-", "+").replace("_", "/")
    padded = key_clean + "=" * ((4 - len(key_clean) % 4) % 4)
    
    try:
        raw_bytes = base64.b64decode(padded)
    except Exception as e:
        print(f"DEBUG: Failed to decode VAPID_PRIVATE_KEY: {e}")
        return key # Fallback to original

    # 4. Re-encode to standard base64 and wrap in PEM
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
        # Use the cleaned PEM key
        private_key_pem = _ensure_pem(settings.VAPID_PRIVATE_KEY)
        
        await asyncio.to_thread(
            webpush,
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=private_key_pem,
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