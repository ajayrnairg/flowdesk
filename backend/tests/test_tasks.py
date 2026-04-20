import pytest
import pytest_asyncio
from httpx import AsyncClient

# Fixture to provide auth headers for user A
@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient) -> dict:
    email = "user_a@example.com"
    password = "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# Fixture to provide auth headers for user B
@pytest_asyncio.fixture
async def auth_headers_b(async_client: AsyncClient) -> dict:
    email = "user_b@example.com"
    password = "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_create_task(async_client: AsyncClient, auth_headers: dict):
    payload = {
        "title": "Buy groceries",
        "scope": "DAILY",
        "priority": "MEDIUM"
    }
    res = await async_client.post("/tasks", json=payload, headers=auth_headers)
    assert res.status_code == 201, f"Failed: {res.text}"
    
    task = res.json()
    assert task["title"] == "Buy groceries"
    assert task["is_done"] is False
    assert "id" in task
    
    # Verify appearance in GET /tasks
    res_get = await async_client.get("/tasks", headers=auth_headers)
    assert res_get.status_code == 200
    tasks = res_get.json()
    assert len(tasks) == 1
    assert tasks[0]["id"] == task["id"]

@pytest.mark.asyncio
async def test_filter_by_scope(async_client: AsyncClient, auth_headers: dict):
    scopes = ["DAILY", "WEEKLY", "MONTHLY"]
    for idx, scope in enumerate(scopes):
        payload = {"title": f"Task {idx}", "scope": scope, "priority": "LOW"}
        await async_client.post("/tasks", json=payload, headers=auth_headers)

    res = await async_client.get("/tasks?scope=WEEKLY", headers=auth_headers)
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) == 1
    assert tasks[0]["scope"] == "WEEKLY"
    assert tasks[0]["title"] == "Task 1"

@pytest.mark.asyncio
async def test_toggle_is_done(async_client: AsyncClient, auth_headers: dict):
    # Create task
    res = await async_client.post("/tasks", json={"title": "Toggle me", "scope": "DAILY"}, headers=auth_headers)
    task_id = res.json()["id"]

    # Toggle to True
    res_toggle = await async_client.patch(f"/tasks/{task_id}/toggle", json={"is_done": True}, headers=auth_headers)
    assert res_toggle.status_code == 200
    assert res_toggle.json()["is_done"] is True

    # Check GET
    res_get = await async_client.get("/tasks", headers=auth_headers)
    tasks = res_get.json()
    task = next(t for t in tasks if t["id"] == task_id)
    assert task["is_done"] is True

@pytest.mark.asyncio
async def test_partial_update(async_client: AsyncClient, auth_headers: dict):
    res = await async_client.post("/tasks", json={"title": "Old title", "scope": "DAILY", "priority": "LOW"}, headers=auth_headers)
    task_id = res.json()["id"]

    # Update only the title
    res_update = await async_client.patch(f"/tasks/{task_id}", json={"title": "New title"}, headers=auth_headers)
    assert res_update.status_code == 200
    task = res_update.json()
    assert task["title"] == "New title"
    assert task["priority"] == "LOW"  # Unchanged

@pytest.mark.asyncio
async def test_delete_task(async_client: AsyncClient, auth_headers: dict):
    res = await async_client.post("/tasks", json={"title": "To be deleted", "scope": "DAILY"}, headers=auth_headers)
    task_id = res.json()["id"]

    res_del = await async_client.delete(f"/tasks/{task_id}", headers=auth_headers)
    assert res_del.status_code == 204

    # Verify absence
    res_get = await async_client.get("/tasks", headers=auth_headers)
    assert not any(t["id"] == task_id for t in res_get.json())

@pytest.mark.asyncio
async def test_ownership(async_client: AsyncClient, auth_headers: dict, auth_headers_b: dict):
    # User A creates a task
    res = await async_client.post("/tasks", json={"title": "User A Task", "scope": "DAILY"}, headers=auth_headers)
    task_id = res.json()["id"]

    # User B tries to PATCH it
    res_patch = await async_client.patch(f"/tasks/{task_id}", json={"title": "Hacked"}, headers=auth_headers_b)
    assert res_patch.status_code == 403

    # User B tries to DELETE it
    res_del = await async_client.delete(f"/tasks/{task_id}", headers=auth_headers_b)
    assert res_del.status_code == 403
    
    # Ensure it's still alive for User A
    res_get = await async_client.get("/tasks", headers=auth_headers)
    assert len(res_get.json()) == 1

@pytest.mark.asyncio
async def test_ordering(async_client: AsyncClient, auth_headers: dict):
    # Create LOW priority done task
    res1 = await async_client.post("/tasks", json={"title": "Low Done", "scope": "DAILY", "priority": "LOW"}, headers=auth_headers)
    await async_client.patch(f"/tasks/{res1.json()['id']}/toggle", json={"is_done": True}, headers=auth_headers)

    # Create HIGH priority undone task
    res2 = await async_client.post("/tasks", json={"title": "High Undone", "scope": "DAILY", "priority": "HIGH"}, headers=auth_headers)

    res_get = await async_client.get("/tasks", headers=auth_headers)
    tasks = res_get.json()
    
    # Expected: High Undone is first, Low Done is second
    assert len(tasks) == 2
    assert tasks[0]["id"] == res2.json()["id"]
    assert tasks[1]["id"] == res1.json()["id"]
