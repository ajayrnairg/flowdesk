import pytest
import pytest_asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from sqlalchemy import select, func

from core.config import settings
from core.database import get_db
from main import app
from models.notification import PushSubscription
from models.user import User
from tests.conftest import TestingSessionLocal

# ── Constants ─────────────────────────────────────────────────────────────────
VALID_TOKEN = settings.NOTIFICATION_SECRET

SUBSCRIPTION_PAYLOAD = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/fake-endpoint-abc123",
    "keys": {
        "p256dh": "BNKjmJ6aXh_dXJK_Wm0ABCDE_fakep256dh_key_here",
        "auth": "fakeAuthKey123",
    },
    "user_agent": "Mozilla/5.0 (test)",
}

INSIDE_UTC = datetime(2026, 4, 21, 1, 5, 0, tzinfo=timezone.utc)
INSIDE_IST = INSIDE_UTC.astimezone(ZoneInfo("Asia/Kolkata"))
OUTSIDE_UTC = datetime(2026, 4, 21, 9, 0, 0, tzinfo=timezone.utc)

# ── DB Helpers ────────────────────────────────────────────────────────────────
async def count_subscriptions(endpoint: str) -> int:
    async with TestingSessionLocal() as session:
        result = await session.execute(
            select(func.count()).select_from(PushSubscription).where(
                PushSubscription.endpoint == endpoint
            )
        )
        return result.scalar_one()

async def get_subscription_id(endpoint: str) -> str:
    async with TestingSessionLocal() as session:
        result = await session.execute(
            select(PushSubscription.id).where(PushSubscription.endpoint == endpoint)
        )
        return str(result.scalar_one())

# ── Mocked-DB helpers ───────────────────────────
def make_mock_db(scalar_result=None) -> AsyncMock:
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = scalar_result
    db = AsyncMock()
    db.execute = AsyncMock(return_value=execute_result)
    return db

def datetime_side_effect(inside_utc: datetime, inside_ist: datetime):
    calls = iter([inside_utc, inside_ist])
    def _now(tz=None):
        return next(calls)
    return _now

# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests (real test DB)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_save_push_subscription(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    res = await client.post(
        "/notifications/subscriptions",
        json=SUBSCRIPTION_PAYLOAD,
    )
    assert res.status_code == 201, res.text
    assert res.json() == {"detail": "Subscription saved"}
    assert await count_subscriptions(SUBSCRIPTION_PAYLOAD["endpoint"]) == 1

@pytest.mark.asyncio
async def test_duplicate_subscription_upsert(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    updated_payload = {
        **SUBSCRIPTION_PAYLOAD,
        "keys": {
            "p256dh": "UPDATED_p256dh_key_value_here",
            "auth": "updatedAuthKey456",
        },
    }
    res1 = await client.post("/notifications/subscriptions", json=SUBSCRIPTION_PAYLOAD)
    res2 = await client.post("/notifications/subscriptions", json=updated_payload)

    assert res1.status_code == 201, res1.text
    assert res2.status_code == 201, res2.text
    assert await count_subscriptions(SUBSCRIPTION_PAYLOAD["endpoint"]) == 1

    async with TestingSessionLocal() as session:
        result = await session.execute(
            select(PushSubscription).where(PushSubscription.endpoint == SUBSCRIPTION_PAYLOAD["endpoint"])
        )
        sub = result.scalar_one()
        assert sub.p256dh == "UPDATED_p256dh_key_value_here"
        assert sub.auth == "updatedAuthKey456"

@pytest.mark.asyncio
async def test_delete_subscription(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    await client.post("/notifications/subscriptions", json=SUBSCRIPTION_PAYLOAD)
    sub_id = await get_subscription_id(SUBSCRIPTION_PAYLOAD["endpoint"])

    res = await client.delete(f"/notifications/subscriptions/{sub_id}")
    assert res.status_code == 204
    assert await count_subscriptions(SUBSCRIPTION_PAYLOAD["endpoint"]) == 0

@pytest.mark.asyncio
async def test_delete_other_user_subscription(authenticated_client, test_user: User, test_user_b: User):
    client_a = await authenticated_client(test_user)
    client_b = await authenticated_client(test_user_b)

    await client_a.post("/notifications/subscriptions", json=SUBSCRIPTION_PAYLOAD)
    sub_id = await get_subscription_id(SUBSCRIPTION_PAYLOAD["endpoint"])

    res = await client_b.delete(f"/notifications/subscriptions/{sub_id}")
    assert res.status_code == 403
    assert await count_subscriptions(SUBSCRIPTION_PAYLOAD["endpoint"]) == 1

@pytest.mark.asyncio
async def test_check_and_send_wrong_token(async_client: AsyncClient):
    res = await async_client.get("/notifications/check-and-send", headers={"X-Notification-Token": "this-is-wrong"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_check_and_send_outside_window(async_client: AsyncClient):
    outside_utc = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)
    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.return_value = outside_utc
        res = await async_client.get("/notifications/check-and-send", headers={"X-Notification-Token": VALID_TOKEN})
    assert res.status_code == 200
    assert res.json() == {"status": "outside_window"}

@pytest.mark.asyncio
async def test_force_send_digest(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    await client.post("/tasks", json={"title": "Morning task", "scope": "DAILY", "priority": "HIGH"})

    mocker.patch("services.email_service.resend.Emails.send", return_value={"id": "mock-email-id"})
    mocker.patch("services.push_service.send_push_notification", new_callable=AsyncMock, return_value=True)

    res = await client.post("/notifications/send-digest", headers={"X-Notification-Token": VALID_TOKEN})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "sent"
    assert body["count"] == 1

# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests (mocked DB)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_inside_window_no_prior_digest_sends(async_client: AsyncClient, mocker):
    mock_db = make_mock_db(scalar_result=None)
    app.dependency_overrides[get_db] = lambda: mock_db
    mock_orchestrator = mocker.patch("routers.notifications.send_morning_digest_to_all_users", new_callable=AsyncMock, return_value=3)

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.side_effect = datetime_side_effect(INSIDE_UTC, INSIDE_IST)
        res = await async_client.get("/notifications/check-and-send", headers={"X-Notification-Token": VALID_TOKEN})

    assert res.status_code == 200
    assert res.json()["status"] == "sent"
    assert res.json()["count"] == 3
    mock_orchestrator.assert_awaited_once()
    
    # Restore the global test DB override
    from tests.conftest import override_get_db
    app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_inside_window_already_sent_skips(async_client: AsyncClient, mocker):
    mock_db = make_mock_db(scalar_result=object())
    app.dependency_overrides[get_db] = lambda: mock_db
    mock_orchestrator = mocker.patch("routers.notifications.send_morning_digest_to_all_users", new_callable=AsyncMock)

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.side_effect = datetime_side_effect(INSIDE_UTC, INSIDE_IST)
        res = await async_client.get("/notifications/check-and-send", headers={"X-Notification-Token": VALID_TOKEN})

    assert res.status_code == 200
    assert res.json() == {"status": "already_sent"}
    mock_orchestrator.assert_not_awaited()
    
    from tests.conftest import override_get_db
    app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_outside_window_returns_outside_window(async_client: AsyncClient, mocker):
    mock_db = make_mock_db()
    app.dependency_overrides[get_db] = lambda: mock_db
    mock_orchestrator = mocker.patch("routers.notifications.send_morning_digest_to_all_users", new_callable=AsyncMock)

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.return_value = OUTSIDE_UTC
        res = await async_client.get("/notifications/check-and-send", headers={"X-Notification-Token": VALID_TOKEN})

    assert res.status_code == 200
    assert res.json() == {"status": "outside_window"}
    mock_db.execute.assert_not_awaited()
    mock_orchestrator.assert_not_awaited()
    
    from tests.conftest import override_get_db
    app.dependency_overrides[get_db] = override_get_db

@pytest.mark.asyncio
async def test_invalid_token_is_rejected(async_client: AsyncClient):
    res = await async_client.get("/notifications/check-and-send", headers={"X-Notification-Token": "wrong-token"})
    assert res.status_code == 403

@pytest.mark.asyncio
async def test_trigger_my_digest_endpoint(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    
    # 1. Test success (digest sent)
    mocker.patch("routers.notifications.send_digest_to_user", new_callable=AsyncMock, return_value=True)
    res = await client.post("/notifications/send-my-digest")
    assert res.status_code == 200
    assert res.json()["status"] == "sent"

    # 2. Test skip (no content)
    mocker.patch("routers.notifications.send_digest_to_user", new_callable=AsyncMock, return_value=False)
    res = await client.post("/notifications/send-my-digest")
    assert res.status_code == 200
    assert res.json()["status"] == "skipped"
