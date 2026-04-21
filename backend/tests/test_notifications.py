"""
tests/test_notifications.py
-----------------------------
Full integration + unit tests for the /notifications router.

Coverage:
  1. test_save_push_subscription        — POST /subscriptions → 201, row in DB
  2. test_duplicate_subscription_upsert — same endpoint twice → count stays 1
  3. test_delete_subscription           — DELETE own → 204, row gone
  4. test_delete_other_user_subscription — DELETE other's → 403
  5. test_check_and_send_wrong_token    — wrong token → 403
  6. test_check_and_send_outside_window — hour=10 UTC → {"status": "outside_window"}
  7. test_force_send_digest             — POST /send-digest with a user + task → count 1,
                                          email + push mocked

Preserved from old file:
  8. test_inside_window_no_prior_digest_sends  — original time-window unit tests
  9. test_inside_window_already_sent_skips
  10. test_outside_window_returns_outside_window
  11. test_invalid_token_is_rejected

Strategy notes:
- Tests 1-4, 7: hit the real test DB via the conftest override_get_db fixture.
  DB state is verified directly through TestingSessionLocal.
- Tests 5-6, 8-11: use mocked datetime / mocked DB sessions.
- Patch targets for services: the definition site (services.email_service,
  services.push_service), NOT the orchestrator's import alias.
"""

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

# 01:05 UTC — inside the default window (DIGEST_HOUR_UTC=1, DIGEST_WINDOW_MINUTES=15)
INSIDE_UTC = datetime(2026, 4, 21, 1, 5, 0, tzinfo=timezone.utc)
INSIDE_IST = INSIDE_UTC.astimezone(ZoneInfo("Asia/Kolkata"))

# 09:00 UTC — outside the window
OUTSIDE_UTC = datetime(2026, 4, 21, 9, 0, 0, tzinfo=timezone.utc)


# ── Auth Fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient) -> dict:
    """Registers + logs in user A, returns Bearer headers."""
    email, password = "notif_a@example.com", "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth_headers_b(async_client: AsyncClient) -> dict:
    """Registers + logs in user B, returns Bearer headers."""
    email, password = "notif_b@example.com", "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ── DB Helpers ────────────────────────────────────────────────────────────────

async def count_subscriptions(endpoint: str) -> int:
    """Count push_subscription rows matching endpoint in the test DB."""
    async with TestingSessionLocal() as session:
        result = await session.execute(
            select(func.count()).select_from(PushSubscription).where(
                PushSubscription.endpoint == endpoint
            )
        )
        return result.scalar_one()


async def get_subscription_id(endpoint: str) -> str:
    """Fetch the UUID of a subscription by endpoint."""
    async with TestingSessionLocal() as session:
        result = await session.execute(
            select(PushSubscription.id).where(PushSubscription.endpoint == endpoint)
        )
        return str(result.scalar_one())


# ── Mocked-DB helpers (for time-window unit tests) ───────────────────────────

def make_mock_db(scalar_result=None) -> AsyncMock:
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = scalar_result
    db = AsyncMock()
    db.execute = AsyncMock(return_value=execute_result)
    return db


def datetime_side_effect(inside_utc: datetime, inside_ist: datetime):
    """Iterator-based side_effect for the two datetime.now() calls in the endpoint."""
    calls = iter([inside_utc, inside_ist])

    def _now(tz=None):
        return next(calls)

    return _now


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Tests (real test DB)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Test 1 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_push_subscription(async_client: AsyncClient, auth_headers: dict):
    """
    POST /notifications/subscriptions with valid data returns 201
    and exactly one row exists in the DB.
    """
    res = await async_client.post(
        "/notifications/subscriptions",
        json=SUBSCRIPTION_PAYLOAD,
        headers=auth_headers,
    )

    assert res.status_code == 201, res.text
    assert res.json() == {"detail": "Subscription saved"}
    assert await count_subscriptions(SUBSCRIPTION_PAYLOAD["endpoint"]) == 1


# ── Test 2 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_duplicate_subscription_upsert(async_client: AsyncClient, auth_headers: dict):
    """
    POSTing the same endpoint twice for the same user must NOT create two rows.
    The second call must update the existing row's keys in-place.
    """
    updated_payload = {
        **SUBSCRIPTION_PAYLOAD,
        "keys": {
            "p256dh": "UPDATED_p256dh_key_value_here",
            "auth": "updatedAuthKey456",
        },
    }

    res1 = await async_client.post(
        "/notifications/subscriptions", json=SUBSCRIPTION_PAYLOAD, headers=auth_headers
    )
    res2 = await async_client.post(
        "/notifications/subscriptions", json=updated_payload, headers=auth_headers
    )

    assert res1.status_code == 201, res1.text
    assert res2.status_code == 201, res2.text

    # Count must still be exactly 1
    assert await count_subscriptions(SUBSCRIPTION_PAYLOAD["endpoint"]) == 1

    # Verify the keys were updated
    async with TestingSessionLocal() as session:
        result = await session.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == SUBSCRIPTION_PAYLOAD["endpoint"]
            )
        )
        sub = result.scalar_one()
        assert sub.p256dh == "UPDATED_p256dh_key_value_here"
        assert sub.auth == "updatedAuthKey456"


# ── Test 3 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_subscription(async_client: AsyncClient, auth_headers: dict):
    """
    DELETE /notifications/subscriptions/{id} returns 204 and the row is gone.
    """
    await async_client.post(
        "/notifications/subscriptions", json=SUBSCRIPTION_PAYLOAD, headers=auth_headers
    )
    sub_id = await get_subscription_id(SUBSCRIPTION_PAYLOAD["endpoint"])

    res = await async_client.delete(
        f"/notifications/subscriptions/{sub_id}", headers=auth_headers
    )

    assert res.status_code == 204, res.text
    assert await count_subscriptions(SUBSCRIPTION_PAYLOAD["endpoint"]) == 0


# ── Test 4 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_other_user_subscription(
    async_client: AsyncClient,
    auth_headers: dict,
    auth_headers_b: dict,
):
    """
    User B attempting to delete User A's subscription must get 403.
    The row must still exist afterwards.
    """
    await async_client.post(
        "/notifications/subscriptions", json=SUBSCRIPTION_PAYLOAD, headers=auth_headers
    )
    sub_id = await get_subscription_id(SUBSCRIPTION_PAYLOAD["endpoint"])

    res = await async_client.delete(
        f"/notifications/subscriptions/{sub_id}", headers=auth_headers_b
    )

    assert res.status_code == 403, res.text
    assert await count_subscriptions(SUBSCRIPTION_PAYLOAD["endpoint"]) == 1


# ── Test 5 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_and_send_wrong_token(async_client: AsyncClient):
    """Wrong token must return 403 before any time-window logic runs."""
    res = await async_client.get(
        "/notifications/check-and-send", params={"token": "this-is-wrong"}
    )
    assert res.status_code == 403, res.text


# ── Test 6 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_and_send_outside_window(async_client: AsyncClient):
    """
    When current UTC hour is 10, returns {"status": "outside_window"}
    without touching the DB or orchestrator.
    """
    outside_utc = datetime(2026, 4, 21, 10, 0, 0, tzinfo=timezone.utc)

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.return_value = outside_utc
        res = await async_client.get(
            "/notifications/check-and-send", params={"token": VALID_TOKEN}
        )

    assert res.status_code == 200, res.text
    assert res.json() == {"status": "outside_window"}


# ── Test 7 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_force_send_digest(async_client: AsyncClient, auth_headers: dict, mocker):
    """
    POST /notifications/send-digest with one user who has a DAILY task.
    Expected: {"status": "sent", "count": 1}.
    email + push mocked so nothing actually sends.
    """
    # Give the registered user a task so the orchestrator's "skip if empty" path
    # is not triggered
    await async_client.post(
        "/tasks",
        json={"title": "Morning task", "scope": "DAILY", "priority": "HIGH"},
        headers=auth_headers,
    )

    # Patch at definition sites — the orchestrator imports these directly
    mocker.patch(
        "services.email_service.resend.Emails.send",
        return_value={"id": "mock-email-id"},
    )
    mocker.patch(
        "services.push_service.send_push_notification",
        new_callable=AsyncMock,
        return_value=True,
    )

    res = await async_client.post(
        "/notifications/send-digest", params={"token": VALID_TOKEN}
    )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "sent"
    assert body["count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Unit Tests (mocked DB — preserved from previous test_notifications.py)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_inside_window_no_prior_digest_sends(async_client: AsyncClient, mocker):
    """01:05 UTC, no prior log → orchestrator called, status=sent."""
    mock_db = make_mock_db(scalar_result=None)
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_orchestrator = mocker.patch(
        "routers.notifications.send_morning_digest_to_all_users",
        new_callable=AsyncMock,
        return_value=3,
    )

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.side_effect = datetime_side_effect(INSIDE_UTC, INSIDE_IST)
        res = await async_client.get(
            "/notifications/check-and-send", params={"token": VALID_TOKEN}
        )

    assert res.status_code == 200, res.text
    assert res.json()["status"] == "sent"
    assert res.json()["count"] == 3
    mock_orchestrator.assert_awaited_once()
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_inside_window_already_sent_skips(async_client: AsyncClient, mocker):
    """01:05 UTC, log row exists → orchestrator NOT called, status=already_sent."""
    mock_db = make_mock_db(scalar_result=object())
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_orchestrator = mocker.patch(
        "routers.notifications.send_morning_digest_to_all_users",
        new_callable=AsyncMock,
    )

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.side_effect = datetime_side_effect(INSIDE_UTC, INSIDE_IST)
        res = await async_client.get(
            "/notifications/check-and-send", params={"token": VALID_TOKEN}
        )

    assert res.status_code == 200, res.text
    assert res.json() == {"status": "already_sent"}
    mock_orchestrator.assert_not_awaited()
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_outside_window_returns_outside_window(async_client: AsyncClient, mocker):
    """09:00 UTC → outside_window, DB never touched."""
    mock_db = make_mock_db()
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_orchestrator = mocker.patch(
        "routers.notifications.send_morning_digest_to_all_users",
        new_callable=AsyncMock,
    )

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.return_value = OUTSIDE_UTC
        res = await async_client.get(
            "/notifications/check-and-send", params={"token": VALID_TOKEN}
        )

    assert res.status_code == 200, res.text
    assert res.json() == {"status": "outside_window"}
    mock_db.execute.assert_not_awaited()
    mock_orchestrator.assert_not_awaited()
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_invalid_token_is_rejected(async_client: AsyncClient):
    """Bad token → 403, regardless of time."""
    res = await async_client.get(
        "/notifications/check-and-send", params={"token": "wrong-token"}
    )
    assert res.status_code == 403
