from pydantic import BaseModel
from typing import Optional


class PushSubscriptionKeys(BaseModel):
    """The 'keys' object from the browser's PushSubscription.toJSON()."""
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    """Request body for POST /notifications/subscriptions."""
    endpoint: str
    keys: PushSubscriptionKeys
    user_agent: Optional[str] = None
