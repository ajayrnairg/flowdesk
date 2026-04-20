"""
tests/test_notifications.py
-----------------------------
Unit tests for the /notifications/check-and-send time-window logic.

Strategy:
- `datetime.now()` is called twice inside the endpoint — once with timezone.utc
  (for time-gating) and once with ZoneInfo("Asia/Kolkata") (for dedup bounds).
  Both calls live at `routers.notifications.datetime`, so that's the patch target.
- The DB is stubbed per-test by overriding FastAPI's `get_db` dependency with an
  AsyncMock, keeping these tests fully in-memory (no NeonDB round-trip).
- `send_morning_digest_to_all_users` is patched at its import site in the router
  module so the orchestrator never fires.
- The valid NOTIFICATION_SECRET is read from settings so the token check passes.
"""

import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient
from core.config import settings
from core.database import get_db
from main import app

# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_TOKEN = settings.NOTIFICATION_SECRET

# 01:05 UTC — inside the default window (DIGEST_HOUR_UTC=1, DIGEST_WINDOW_MINUTES=15)
INSIDE_UTC = datetime(2026, 4, 21, 1, 5, 0, tzinfo=timezone.utc)
INSIDE_IST = INSIDE_UTC.astimezone(ZoneInfo("Asia/Kolkata"))

# 09:00 UTC — outside the window
OUTSIDE_UTC = datetime(2026, 4, 21, 9, 0, 0, tzinfo=timezone.utc)


def make_mock_db(scalar_result=None) -> AsyncMock:
    """
    Build a minimal AsyncSession mock whose execute().scalar_one_or_none()
    returns scalar_result.
    
    scalar_result=None  → no digest sent today (trigger the orchestrator)
    scalar_result=<obj> → a NotificationLog row exists (already sent)
    """
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = scalar_result

    db = AsyncMock()
    db.execute = AsyncMock(return_value=execute_result)
    return db


def datetime_side_effect(inside_utc: datetime, inside_ist: datetime):
    """
    Returns a side_effect function that mimics the two datetime.now() calls
    inside the endpoint:
      1st call: datetime.now(timezone.utc)  → inside_utc
      2nd call: datetime.now(ZoneInfo(...)) → inside_ist
    Raises TypeError for any unexpected signature.
    """
    calls = iter([inside_utc, inside_ist])

    def _now(tz=None):
        return next(calls)

    return _now


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inside_window_no_prior_digest_sends(async_client: AsyncClient, mocker):
    """
    Scenario 1: 01:05 UTC, no NotificationLog row for today.
    Expected: orchestrator is called, response is {"status": "sent", "count": <n>}.
    """
    mock_db = make_mock_db(scalar_result=None)  # no prior digest
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_orchestrator = mocker.patch(
        "routers.notifications.send_morning_digest_to_all_users",
        new_callable=AsyncMock,
        return_value=3,  # pretend 3 users were notified
    )

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.side_effect = datetime_side_effect(INSIDE_UTC, INSIDE_IST)

        res = await async_client.get(
            "/notifications/check-and-send",
            params={"token": VALID_TOKEN},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "sent"
    assert body["count"] == 3
    mock_orchestrator.assert_awaited_once()

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_inside_window_already_sent_skips(async_client: AsyncClient, mocker):
    """
    Scenario 2: 01:05 UTC, NotificationLog already has a 'sent' row for today.
    Expected: orchestrator is NOT called, response is {"status": "already_sent"}.
    """
    # Return a truthy sentinel — any non-None value means a row was found
    mock_db = make_mock_db(scalar_result=object())
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_orchestrator = mocker.patch(
        "routers.notifications.send_morning_digest_to_all_users",
        new_callable=AsyncMock,
    )

    with patch("routers.notifications.datetime") as mock_dt:
        mock_dt.now.side_effect = datetime_side_effect(INSIDE_UTC, INSIDE_IST)

        res = await async_client.get(
            "/notifications/check-and-send",
            params={"token": VALID_TOKEN},
        )

    assert res.status_code == 200, res.text
    assert res.json() == {"status": "already_sent"}
    mock_orchestrator.assert_not_awaited()

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_outside_window_returns_outside_window(async_client: AsyncClient, mocker):
    """
    Scenario 3: 09:00 UTC — outside the digest window entirely.
    Expected: early return {"status": "outside_window"}, DB never touched,
              orchestrator never called.
    """
    mock_db = make_mock_db()
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_orchestrator = mocker.patch(
        "routers.notifications.send_morning_digest_to_all_users",
        new_callable=AsyncMock,
    )

    with patch("routers.notifications.datetime") as mock_dt:
        # Only the first datetime.now() call is made before the early return
        mock_dt.now.return_value = OUTSIDE_UTC

        res = await async_client.get(
            "/notifications/check-and-send",
            params={"token": VALID_TOKEN},
        )

    assert res.status_code == 200, res.text
    assert res.json() == {"status": "outside_window"}
    mock_db.execute.assert_not_awaited()   # DB should never be touched
    mock_orchestrator.assert_not_awaited()

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_invalid_token_is_rejected(async_client: AsyncClient):
    """
    Sanity guard: a bad token must return 403 regardless of time.
    No mocking needed — the token check runs before any datetime logic.
    """
    res = await async_client.get(
        "/notifications/check-and-send",
        params={"token": "wrong-token"},
    )
    assert res.status_code == 403
