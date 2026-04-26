import pytest
from httpx import AsyncClient
from models.user import User

@pytest.mark.asyncio
async def test_create_task(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    payload = {
        "title": "Buy groceries",
        "scope": "DAILY",
        "priority": "MEDIUM"
    }
    res = await client.post("/tasks", json=payload)
    assert res.status_code == 201, f"Failed: {res.text}"
    
    task = res.json()
    assert task["title"] == "Buy groceries"
    assert task["is_done"] is False
    assert "id" in task
    
    # Verify appearance in GET /tasks
    res_get = await client.get("/tasks")
    assert res_get.status_code == 200
    tasks = res_get.json()
    assert len(tasks) == 1
    assert tasks[0]["id"] == task["id"]

@pytest.mark.asyncio
async def test_filter_by_scope(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    scopes = ["DAILY", "WEEKLY", "MONTHLY"]
    for idx, scope in enumerate(scopes):
        payload = {"title": f"Task {idx}", "scope": scope, "priority": "LOW"}
        await client.post("/tasks", json=payload)

    res = await client.get("/tasks?scope=WEEKLY")
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) == 1
    assert tasks[0]["scope"] == "WEEKLY"
    assert tasks[0]["title"] == "Task 1"

@pytest.mark.asyncio
async def test_toggle_is_done(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    # Create task
    res = await client.post("/tasks", json={"title": "Toggle me", "scope": "DAILY"})
    task_id = res.json()["id"]

    # Toggle to True
    res_toggle = await client.patch(f"/tasks/{task_id}/toggle", json={"is_done": True})
    assert res_toggle.status_code == 200
    assert res_toggle.json()["is_done"] is True

    # Check GET
    res_get = await client.get("/tasks")
    tasks = res_get.json()
    task = next(t for t in tasks if t["id"] == task_id)
    assert task["is_done"] is True

@pytest.mark.asyncio
async def test_partial_update(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    res = await client.post("/tasks", json={"title": "Old title", "scope": "DAILY", "priority": "LOW"})
    task_id = res.json()["id"]

    # Update only the title
    res_update = await client.patch(f"/tasks/{task_id}", json={"title": "New title"})
    assert res_update.status_code == 200
    task = res_update.json()
    assert task["title"] == "New title"
    assert task["priority"] == "LOW"  # Unchanged

@pytest.mark.asyncio
async def test_delete_task(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    res = await client.post("/tasks", json={"title": "To be deleted", "scope": "DAILY"})
    task_id = res.json()["id"]

    res_del = await client.delete(f"/tasks/{task_id}")
    assert res_del.status_code == 204

    # Verify absence
    res_get = await client.get("/tasks")
    assert not any(t["id"] == task_id for t in res_get.json())

@pytest.mark.asyncio
async def test_ownership(authenticated_client, test_user: User, test_user_b: User):
    client_a = await authenticated_client(test_user)
    client_b = await authenticated_client(test_user_b)

    # User A creates a task
    res = await client_a.post("/tasks", json={"title": "User A Task", "scope": "DAILY"})
    task_id = res.json()["id"]

    # User B tries to PATCH it
    res_patch = await client_b.patch(f"/tasks/{task_id}", json={"title": "Hacked"})
    assert res_patch.status_code == 403

    # User B tries to DELETE it
    res_del = await client_b.delete(f"/tasks/{task_id}")
    assert res_del.status_code == 403
    
    # Ensure it's still alive for User A
    res_get = await client_a.get("/tasks")
    assert len(res_get.json()) == 1

@pytest.mark.asyncio
async def test_ordering(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    # Create LOW priority done task
    res1 = await client.post("/tasks", json={"title": "Low Done", "scope": "DAILY", "priority": "LOW"})
    await client.patch(f"/tasks/{res1.json()['id']}/toggle", json={"is_done": True})

    # Create HIGH priority undone task
    res2 = await client.post("/tasks", json={"title": "High Undone", "scope": "DAILY", "priority": "HIGH"})

    res_get = await client.get("/tasks")
    tasks = res_get.json()
    
    # Expected: High Undone is first, Low Done is second
    assert len(tasks) == 2
    assert tasks[0]["id"] == res2.json()["id"]
    assert tasks[1]["id"] == res1.json()["id"]
    
@pytest.mark.asyncio
async def test_create_recurring_task(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    payload = {
        "title": "Daily Workout",
        "scope": "DAILY",
        "is_recurring": True
    }
    res = await client.post("/tasks", json=payload)
    assert res.status_code == 201
    assert res.json()["is_recurring"] is True
