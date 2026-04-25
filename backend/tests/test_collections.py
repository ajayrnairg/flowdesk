import asyncio
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import event, text, select
from datetime import datetime, timezone

from tests.conftest import TestingSessionLocal, engine_test
from models.knowledge import KnowledgeItem, Collection, CollectionItem
from services.auto_collection_service import auto_add_to_collection

@pytest_asyncio.fixture
async def auth_data(async_client: AsyncClient) -> dict:
    email = f"user_{uuid.uuid4()}@example.com"
    password = "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    
    # Get user details
    me_res = await async_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = uuid.UUID(me_res.json()["id"])
    
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "user_id": user_id
    }

@pytest_asyncio.fixture
async def auth_data_b(async_client: AsyncClient) -> dict:
    email = f"user_{uuid.uuid4()}@example.com"
    password = "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}}

@pytest_asyncio.fixture
async def db():
    async with TestingSessionLocal() as session:
        yield session

async def create_test_item(db, user_id, content_type="article"):
    item = KnowledgeItem(
        user_id=user_id,
        url=f"https://example.com/{uuid.uuid4()}",
        title=f"Test {content_type}",
        content_type=content_type,
        status="done",
        read_status="UNREAD"
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

@pytest.mark.asyncio
async def test_auto_collection_creates_default_on_first_save(async_client: AsyncClient, auth_data: dict, db):
    user_id = auth_data["user_id"]
    headers = auth_data["headers"]

    item = await create_test_item(db, user_id, "article")
    await auto_add_to_collection(item.id, user_id, "article", db)

    res = await async_client.get("/collections", headers=headers)
    assert res.status_code == 200
    collections = res.json()
    assert len(collections) == 1
    assert collections[0]["name"] == "📰 Articles"
    assert collections[0]["is_default"] is True
    assert collections[0]["item_count"] == 1

@pytest.mark.asyncio
async def test_twitter_and_linkedin_share_same_collection(async_client: AsyncClient, auth_data: dict, db):
    user_id = auth_data["user_id"]
    headers = auth_data["headers"]

    item1 = await create_test_item(db, user_id, "twitter")
    item2 = await create_test_item(db, user_id, "linkedin")

    await auto_add_to_collection(item1.id, user_id, "twitter", db)
    await auto_add_to_collection(item2.id, user_id, "linkedin", db)

    res = await async_client.get("/collections", headers=headers)
    assert res.status_code == 200
    collections = res.json()
    assert len(collections) == 1
    assert collections[0]["name"] == "💬 Social Saves"
    assert collections[0]["item_count"] == 2

@pytest.mark.asyncio
async def test_auto_collection_is_idempotent(async_client: AsyncClient, auth_data: dict, db):
    user_id = auth_data["user_id"]
    headers = auth_data["headers"]

    item = await create_test_item(db, user_id, "youtube")

    # Call it twice
    await auto_add_to_collection(item.id, user_id, "youtube", db)
    await auto_add_to_collection(item.id, user_id, "youtube", db)

    res = await async_client.get("/collections", headers=headers)
    collections = res.json()
    coll_id = collections[0]["id"]

    items_res = await async_client.get(f"/collections/{coll_id}/items", headers=headers)
    assert items_res.status_code == 200
    items = items_res.json()
    assert len(items) == 1

@pytest.mark.asyncio
async def test_create_custom_collection(async_client: AsyncClient, auth_data: dict):
    headers = auth_data["headers"]

    res = await async_client.post(
        "/collections",
        json={"name": "Python Deep Dives", "color": "#10B981"},
        headers=headers
    )
    assert res.status_code == 201
    coll = res.json()
    assert coll["name"] == "Python Deep Dives"
    assert coll["color"] == "#10B981"
    assert coll["is_default"] is False

    list_res = await async_client.get("/collections", headers=headers)
    collections = list_res.json()
    assert len(collections) == 1
    assert collections[0]["name"] == "Python Deep Dives"

@pytest.mark.asyncio
async def test_add_item_to_custom_collection(async_client: AsyncClient, auth_data: dict, db):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    item = await create_test_item(db, user_id)
    
    coll_res = await async_client.post(
        "/collections",
        json={"name": "My Custom"},
        headers=headers
    )
    coll_id = coll_res.json()["id"]

    add_res = await async_client.post(
        f"/collections/{coll_id}/items",
        json={"knowledge_item_id": str(item.id)},
        headers=headers
    )
    assert add_res.status_code == 201

    items_res = await async_client.get(f"/collections/{coll_id}/items", headers=headers)
    assert len(items_res.json()) == 1
    assert items_res.json()[0]["id"] == str(item.id)

@pytest.mark.asyncio
async def test_add_item_duplicate_returns_409(async_client: AsyncClient, auth_data: dict, db):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    item = await create_test_item(db, user_id)
    coll_res = await async_client.post("/collections", json={"name": "DupTest"}, headers=headers)
    coll_id = coll_res.json()["id"]

    await async_client.post(
        f"/collections/{coll_id}/items",
        json={"knowledge_item_id": str(item.id)},
        headers=headers
    )
    
    add_res_2 = await async_client.post(
        f"/collections/{coll_id}/items",
        json={"knowledge_item_id": str(item.id)},
        headers=headers
    )
    assert add_res_2.status_code == 409

@pytest.mark.asyncio
async def test_remove_item_from_collection_does_not_delete_item(async_client: AsyncClient, auth_data: dict, db):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    item = await create_test_item(db, user_id)
    coll_res = await async_client.post("/collections", json={"name": "DelTest"}, headers=headers)
    coll_id = coll_res.json()["id"]

    await async_client.post(
        f"/collections/{coll_id}/items",
        json={"knowledge_item_id": str(item.id)},
        headers=headers
    )

    del_res = await async_client.delete(f"/collections/{coll_id}/items/{item.id}", headers=headers)
    assert del_res.status_code == 204

    # Item gone from collection
    items_res = await async_client.get(f"/collections/{coll_id}/items", headers=headers)
    assert len(items_res.json()) == 0

    # Item still in DB
    stmt = select(KnowledgeItem).where(KnowledgeItem.id == item.id)
    result = await db.execute(stmt)
    assert result.scalar_one_or_none() is not None

@pytest.mark.asyncio
async def test_delete_default_collection_forbidden(async_client: AsyncClient, auth_data: dict, db):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    item = await create_test_item(db, user_id, "article")
    await auto_add_to_collection(item.id, user_id, "article", db)

    colls = await async_client.get("/collections", headers=headers)
    coll_id = colls.json()[0]["id"]

    del_res = await async_client.delete(f"/collections/{coll_id}", headers=headers)
    assert del_res.status_code == 403

@pytest.mark.asyncio
async def test_delete_custom_collection_succeeds(async_client: AsyncClient, auth_data: dict):
    headers = auth_data["headers"]

    coll_res = await async_client.post("/collections", json={"name": "DelCustom"}, headers=headers)
    coll_id = coll_res.json()["id"]

    del_res = await async_client.delete(f"/collections/{coll_id}", headers=headers)
    assert del_res.status_code == 204

    colls = await async_client.get("/collections", headers=headers)
    assert len(colls.json()) == 0

@pytest.mark.asyncio
async def test_read_status_update_to_done_sets_read_at(async_client: AsyncClient, auth_data: dict, db):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    item = await create_test_item(db, user_id)

    res = await async_client.patch(
        f"/knowledge/{item.id}/read-status",
        json={"read_status": "DONE"},
        headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["read_status"] == "DONE"
    assert data["read_at"] is not None
    assert data["last_opened_at"] is not None

@pytest.mark.asyncio
async def test_read_status_update_always_sets_last_opened_at(async_client: AsyncClient, auth_data: dict, db):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    item = await create_test_item(db, user_id)

    res = await async_client.patch(
        f"/knowledge/{item.id}/read-status",
        json={"read_status": "READING"},
        headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["read_status"] == "READING"
    assert data["read_at"] is None
    assert data["last_opened_at"] is not None

@pytest.mark.asyncio
async def test_library_endpoint_returns_all_collections_with_items(async_client: AsyncClient, auth_data: dict, db):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    c1 = await async_client.post("/collections", json={"name": "C1"}, headers=headers)
    c2 = await async_client.post("/collections", json={"name": "C2"}, headers=headers)
    
    item1 = await create_test_item(db, user_id)
    item2 = await create_test_item(db, user_id)

    await async_client.post(f"/collections/{c1.json()['id']}/items", json={"knowledge_item_id": str(item1.id)}, headers=headers)
    await async_client.post(f"/collections/{c2.json()['id']}/items", json={"knowledge_item_id": str(item2.id)}, headers=headers)

    lib = await async_client.get("/collections/library/overview", headers=headers)
    assert lib.status_code == 200
    data = lib.json()
    
    assert data["total_items"] == 2
    assert len(data["collections"]) == 2
    for c in data["collections"]:
        assert len(c["items"]) == 1

@pytest.mark.asyncio
async def test_library_items_capped_at_10_per_shelf(async_client: AsyncClient, auth_data: dict, db):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    c1 = await async_client.post("/collections", json={"name": "BigC"}, headers=headers)
    cid = c1.json()["id"]

    for _ in range(15):
        it = await create_test_item(db, user_id)
        await async_client.post(f"/collections/{cid}/items", json={"knowledge_item_id": str(it.id)}, headers=headers)

    lib = await async_client.get("/collections/library/overview", headers=headers)
    data = lib.json()
    
    coll = data["collections"][0]
    assert coll["item_count"] == 15
    assert len(coll["items"]) == 10

@pytest.mark.asyncio
async def test_ownership(async_client: AsyncClient, auth_data: dict, auth_data_b: dict, db):
    headers_a = auth_data["headers"]
    headers_b = auth_data_b["headers"]

    coll_a = await async_client.post("/collections", json={"name": "UserA Coll"}, headers=headers_a)
    cid = coll_a.json()["id"]

    # User B tries to read User A's collection
    res = await async_client.get(f"/collections/{cid}/items", headers=headers_b)
    assert res.status_code == 404

@pytest_asyncio.fixture
def query_counter():
    count = []
    
    def count_queries(conn, cursor, statement, parameters, context, executemany):
        count.append(1)

    event.listen(engine_test.sync_engine, "before_cursor_execute", count_queries)
    yield count
    event.remove(engine_test.sync_engine, "before_cursor_execute", count_queries)

@pytest.mark.asyncio
async def test_library_uses_two_queries_not_n_plus_one(async_client: AsyncClient, auth_data: dict, db, query_counter: list):
    headers = auth_data["headers"]
    user_id = auth_data["user_id"]

    # Create 5 collections, 3 items each
    for i in range(5):
        c = await async_client.post("/collections", json={"name": f"Col{i}"}, headers=headers)
        cid = c.json()["id"]
        for j in range(3):
            it = await create_test_item(db, user_id)
            await async_client.post(f"/collections/{cid}/items", json={"knowledge_item_id": str(it.id)}, headers=headers)

    query_counter.clear()

    # Hit the library endpoint
    res = await async_client.get("/collections/library/overview", headers=headers)
    assert res.status_code == 200
    
    # Check that N+1 is avoided. 2 queries for library, plus up to 2 for auth/user lookup. Max 4.
    assert len(query_counter) <= 4
