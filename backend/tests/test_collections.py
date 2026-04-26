import asyncio
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import event, select
from models.user import User
from models.knowledge import KnowledgeItem
from services.auto_collection_service import auto_add_to_collection
from tests.conftest import TestingSessionLocal, engine_test

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
async def test_auto_collection_creates_default_on_first_save(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item = await create_test_item(db, test_user.id, "article")
    await auto_add_to_collection(item.id, test_user.id, "article", db)

    res = await client.get("/collections")
    assert res.status_code == 200
    collections = res.json()
    assert len(collections) == 1
    assert collections[0]["name"] == "📰 Articles"
    assert collections[0]["is_default"] is True
    assert collections[0]["item_count"] == 1

@pytest.mark.asyncio
async def test_twitter_and_linkedin_share_same_collection(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item1 = await create_test_item(db, test_user.id, "twitter")
    item2 = await create_test_item(db, test_user.id, "linkedin")

    await auto_add_to_collection(item1.id, test_user.id, "twitter", db)
    await auto_add_to_collection(item2.id, test_user.id, "linkedin", db)

    res = await client.get("/collections")
    assert res.status_code == 200
    collections = res.json()
    assert len(collections) == 1
    assert collections[0]["name"] == "💬 Social Saves"
    assert collections[0]["item_count"] == 2

@pytest.mark.asyncio
async def test_auto_collection_is_idempotent(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item = await create_test_item(db, test_user.id, "youtube")

    # Call it twice
    await auto_add_to_collection(item.id, test_user.id, "youtube", db)
    await auto_add_to_collection(item.id, test_user.id, "youtube", db)

    res = await client.get("/collections")
    collections = res.json()
    coll_id = collections[0]["id"]

    items_res = await client.get(f"/collections/{coll_id}/items")
    assert items_res.status_code == 200
    items = items_res.json()
    assert len(items) == 1

@pytest.mark.asyncio
async def test_create_custom_collection(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    res = await client.post(
        "/collections",
        json={"name": "Python Deep Dives", "color": "#10B981"}
    )
    assert res.status_code == 201
    coll = res.json()
    assert coll["name"] == "Python Deep Dives"
    assert coll["color"] == "#10B981"
    assert coll["is_default"] is False

    list_res = await client.get("/collections")
    collections = list_res.json()
    assert len(collections) == 1
    assert collections[0]["name"] == "Python Deep Dives"

@pytest.mark.asyncio
async def test_add_item_to_custom_collection(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item = await create_test_item(db, test_user.id)
    
    coll_res = await client.post("/collections", json={"name": "My Custom"})
    coll_id = coll_res.json()["id"]

    add_res = await client.post(
        f"/collections/{coll_id}/items",
        json={"knowledge_item_id": str(item.id)}
    )
    assert add_res.status_code == 201

    items_res = await client.get(f"/collections/{coll_id}/items")
    assert len(items_res.json()) == 1
    assert items_res.json()[0]["id"] == str(item.id)

@pytest.mark.asyncio
async def test_add_item_duplicate_returns_409(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item = await create_test_item(db, test_user.id)
    coll_res = await client.post("/collections", json={"name": "DupTest"})
    coll_id = coll_res.json()["id"]

    await client.post(
        f"/collections/{coll_id}/items",
        json={"knowledge_item_id": str(item.id)}
    )
    
    add_res_2 = await client.post(
        f"/collections/{coll_id}/items",
        json={"knowledge_item_id": str(item.id)}
    )
    assert add_res_2.status_code == 409

@pytest.mark.asyncio
async def test_remove_item_from_collection_does_not_delete_item(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item = await create_test_item(db, test_user.id)
    coll_res = await client.post("/collections", json={"name": "DelTest"})
    coll_id = coll_res.json()["id"]

    await client.post(
        f"/collections/{coll_id}/items",
        json={"knowledge_item_id": str(item.id)}
    )

    del_res = await client.delete(f"/collections/{coll_id}/items/{item.id}")
    assert del_res.status_code == 204

    # Item gone from collection
    items_res = await client.get(f"/collections/{coll_id}/items")
    assert len(items_res.json()) == 0

    # Item still in DB
    stmt = select(KnowledgeItem).where(KnowledgeItem.id == item.id)
    result = await db.execute(stmt)
    assert result.scalar_one_or_none() is not None

@pytest.mark.asyncio
async def test_delete_default_collection_forbidden(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item = await create_test_item(db, test_user.id, "article")
    await auto_add_to_collection(item.id, test_user.id, "article", db)

    colls = await client.get("/collections")
    coll_id = colls.json()[0]["id"]

    del_res = await client.delete(f"/collections/{coll_id}")
    assert del_res.status_code == 403

@pytest.mark.asyncio
async def test_delete_custom_collection_succeeds(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    coll_res = await client.post("/collections", json={"name": "DelCustom"})
    coll_id = coll_res.json()["id"]

    del_res = await client.delete(f"/collections/{coll_id}")
    assert del_res.status_code == 204

    colls = await client.get("/collections")
    assert len(colls.json()) == 0

@pytest.mark.asyncio
async def test_read_status_update_to_done_sets_read_at(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item = await create_test_item(db, test_user.id)

    res = await client.patch(
        f"/knowledge/{item.id}/read-status",
        json={"read_status": "DONE"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["read_status"] == "DONE"
    assert data["read_at"] is not None
    assert data["last_opened_at"] is not None

@pytest.mark.asyncio
async def test_read_status_update_always_sets_last_opened_at(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    item = await create_test_item(db, test_user.id)

    res = await client.patch(
        f"/knowledge/{item.id}/read-status",
        json={"read_status": "READING"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["read_status"] == "READING"
    assert data["read_at"] is None
    assert data["last_opened_at"] is not None

@pytest.mark.asyncio
async def test_library_endpoint_returns_all_collections_with_items(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    c1 = await client.post("/collections", json={"name": "C1"})
    c2 = await client.post("/collections", json={"name": "C2"})
    
    item1 = await create_test_item(db, test_user.id)
    item2 = await create_test_item(db, test_user.id)

    await client.post(f"/collections/{c1.json()['id']}/items", json={"knowledge_item_id": str(item1.id)})
    await client.post(f"/collections/{c2.json()['id']}/items", json={"knowledge_item_id": str(item2.id)})

    lib = await client.get("/collections/library/overview")
    assert lib.status_code == 200
    data = lib.json()
    
    assert data["total_items"] == 2
    assert len(data["collections"]) == 2
    for c in data["collections"]:
        assert len(c["items"]) == 1

@pytest.mark.asyncio
async def test_library_items_capped_at_10_per_shelf(authenticated_client, test_user: User, db):
    client = await authenticated_client(test_user)
    c1 = await client.post("/collections", json={"name": "BigC"})
    cid = c1.json()["id"]

    for _ in range(15):
        it = await create_test_item(db, test_user.id)
        await client.post(f"/collections/{cid}/items", json={"knowledge_item_id": str(it.id)})

    lib = await client.get("/collections/library/overview")
    data = lib.json()
    
    coll = data["collections"][0]
    assert coll["item_count"] == 15
    assert len(coll["items"]) == 10

@pytest.mark.asyncio
async def test_ownership(authenticated_client, test_user: User, test_user_b: User, db):
    client_b = await authenticated_client(test_user_b)
    client_a = await authenticated_client(test_user)

    coll_a = await client_a.post("/collections", json={"name": "UserA Coll"})
    cid = coll_a.json()["id"]

    # User B tries to read User A's collection
    res = await client_b.get(f"/collections/{cid}/items")
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
async def test_library_uses_two_queries_not_n_plus_one(authenticated_client, test_user: User, db, query_counter: list):
    client = await authenticated_client(test_user)
    for i in range(5):
        c = await client.post("/collections", json={"name": f"Col{i}"})
        cid = c.json()["id"]
        for j in range(3):
            it = await create_test_item(db, test_user.id)
            await client.post(f"/collections/{cid}/items", json={"knowledge_item_id": str(it.id)})

    query_counter.clear()
    res = await client.get("/collections/library/overview")
    assert res.status_code == 200
    # 2 for library, plus dependency overhead. N+1 should be avoided.
    assert len(query_counter) <= 4
