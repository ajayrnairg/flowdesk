import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.future import select

from models.user import User
from models.knowledge import KnowledgeItem, ItemStatus
from tests.conftest import TestingSessionLocal

@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient) -> dict:
    email = "search_user_a@example.com"
    password = "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture
async def auth_headers_b(async_client: AsyncClient) -> dict:
    email = "search_user_b@example.com"
    password = "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest_asyncio.fixture
async def user_a(async_client: AsyncClient, auth_headers: dict) -> User:
    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "search_user_a@example.com"))
        return result.scalar_one()

@pytest_asyncio.fixture
async def user_b(async_client: AsyncClient, auth_headers_b: dict) -> User:
    async with TestingSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "search_user_b@example.com"))
        return result.scalar_one()

@pytest.mark.asyncio
async def test_semantic_search_returns_answer(async_client: AsyncClient, auth_headers: dict, user_a: User, mocker):
    # Setup: create a KnowledgeItem
    item_id = uuid.uuid4()
    async with TestingSessionLocal() as db:
        item = KnowledgeItem(
            id=item_id,
            user_id=user_a.id,
            url="https://example.com/test",
            title="Test Item",
            raw_text="Some text",
            content_type="article",
            status=ItemStatus.DONE.value,
            is_processed=True
        )
        db.add(item)
        await db.commit()

    # Mocks
    mocker.patch("services.embedding_service.embed_query", return_value=[0.1] * 768)
    
    mock_chunks = [
        {
            "chunk_text": "chunk 1",
            "chunk_index": 0,
            "distance": 0.1,
            "knowledge_item_id": item_id,
            "item_title": "Test Item",
            "item_url": "https://example.com/test",
            "item_content_type": "article",
            "chunk_excerpt": "chunk 1 excerpt"
        },
        {
            "chunk_text": "chunk 2",
            "chunk_index": 1,
            "distance": 0.4,
            "knowledge_item_id": item_id,
            "item_title": "Test Item",
            "item_url": "https://example.com/test",
            "item_content_type": "article",
            "chunk_excerpt": "chunk 2 excerpt"
        }
    ]
    mocker.patch("routers.search.semantic_search", return_value=mock_chunks)
    mocker.patch("routers.search.synthesise_answer", return_value="This is the synthesised answer.")
    mocker.patch("routers.search.get_cached_search", return_value=None)
    mocker.patch("routers.search.cache_search_result", return_value=None)

    # Execute
    res = await async_client.post(
        "/search",
        json={"query": "test query"},
        headers=auth_headers
    )
    
    # Assert
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "This is the synthesised answer."
    assert len(data["sources"]) == 2
    assert data["cached"] is False
    assert isinstance(data["took_ms"], int) and data["took_ms"] >= 0

@pytest.mark.asyncio
async def test_cache_hit_returns_cached_result(async_client: AsyncClient, auth_headers: dict, mocker):
    item_id = uuid.uuid4()
    cached_response = {
        "query": "cached query",
        "answer": "Cached answer.",
        "sources": [
            {
                "knowledge_item_id": str(item_id),
                "title": "Cached Title",
                "content_type": "article",
                "url": "https://example.com/cache",
                "chunk_excerpt": "cached excerpt",
                "similarity_score": 0.95
            }
        ]
        # cached and took_ms are omitted intentionally from the mock
        # to test that the router injects them
    }
    
    mocker.patch("routers.search.get_cached_search", return_value=cached_response)
    mock_semantic_search = mocker.patch("routers.search.semantic_search")

    res = await async_client.post(
        "/search",
        json={"query": "cached query"},
        headers=auth_headers
    )
    
    assert res.status_code == 200
    data = res.json()
    assert data["cached"] is True
    assert data["answer"] == "Cached answer."
    mock_semantic_search.assert_not_called()

@pytest.mark.asyncio
async def test_empty_knowledge_base_returns_graceful_message(async_client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch("routers.search.get_cached_search", return_value=None)
    mocker.patch("routers.search.semantic_search", return_value=[])
    mocker.patch("routers.search.synthesise_answer", return_value="I could not find relevant information in your knowledge base for this query.")
    
    res = await async_client.post(
        "/search",
        json={"query": "no matches"},
        headers=auth_headers
    )
    
    assert res.status_code == 200
    assert "could not find relevant" in res.json()["answer"]

@pytest.mark.asyncio
async def test_query_too_short_returns_422(async_client: AsyncClient, auth_headers: dict):
    res = await async_client.post(
        "/search",
        json={"query": "a"},
        headers=auth_headers
    )
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_reindex_endpoint(async_client: AsyncClient, auth_headers: dict, user_a: User, mocker):
    item_id = uuid.uuid4()
    async with TestingSessionLocal() as db:
        item = KnowledgeItem(
            id=item_id,
            user_id=user_a.id,
            content_type="article",
            status=ItemStatus.DONE.value
        )
        db.add(item)
        await db.commit()

    mocker.patch("routers.search.index_knowledge_item", return_value=None)

    res = await async_client.get(
        f"/search/reindex/{item_id}",
        headers=auth_headers
    )
    assert res.status_code == 200
    assert res.json() == {"status": "reindexed", "item_id": str(item_id)}

@pytest.mark.asyncio
async def test_reindex_other_user_item(async_client: AsyncClient, auth_headers_b: dict, user_a: User, mocker):
    item_id = uuid.uuid4()
    async with TestingSessionLocal() as db:
        # Create item owned by user A
        item = KnowledgeItem(
            id=item_id,
            user_id=user_a.id,
            content_type="article",
            status=ItemStatus.DONE.value
        )
        db.add(item)
        await db.commit()

    mocker.patch("routers.search.index_knowledge_item", return_value=None)

    # User B tries to reindex it
    res = await async_client.get(
        f"/search/reindex/{item_id}",
        headers=auth_headers_b
    )
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_similarity_score_is_between_0_and_1(async_client: AsyncClient, auth_headers: dict, user_a: User, mocker):
    item_id = uuid.uuid4()
    mocker.patch("routers.search.get_cached_search", return_value=None)
    mocker.patch("routers.search.synthesise_answer", return_value="Test")
    mocker.patch("routers.search.cache_search_result", return_value=None)
    
    mock_chunks = [
        {
            "chunk_text": "1", "chunk_index": 0, "distance": 0.1,
            "knowledge_item_id": item_id, "item_title": "A", "item_url": "A", "item_content_type": "article", "chunk_excerpt": "1"
        },
        {
            "chunk_text": "2", "chunk_index": 1, "distance": 0.4,
            "knowledge_item_id": item_id, "item_title": "B", "item_url": "B", "item_content_type": "article", "chunk_excerpt": "2"
        },
        {
            "chunk_text": "3", "chunk_index": 2, "distance": 0.8,
            "knowledge_item_id": item_id, "item_title": "C", "item_url": "C", "item_content_type": "article", "chunk_excerpt": "3"
        }
    ]
    mocker.patch("routers.search.semantic_search", return_value=mock_chunks)

    res = await async_client.post(
        "/search",
        json={"query": "test query"},
        headers=auth_headers
    )
    
    assert res.status_code == 200
    sources = res.json()["sources"]
    assert len(sources) == 3
    
    assert sources[0]["similarity_score"] == 0.9
    assert sources[1]["similarity_score"] == 0.6
    assert sources[2]["similarity_score"] == 0.2
    
    for source in sources:
        assert 0.0 <= source["similarity_score"] <= 1.0

@pytest.mark.asyncio
async def test_cache_write_failure_does_not_break_search(async_client: AsyncClient, auth_headers: dict, user_a: User, mocker):
    item_id = uuid.uuid4()
    
    mock_chunks = [
        {
            "chunk_text": "1", "chunk_index": 0, "distance": 0.1,
            "knowledge_item_id": item_id, "item_title": "A", "item_url": "A", "item_content_type": "article", "chunk_excerpt": "1"
        }
    ]
    
    mocker.patch("routers.search.get_cached_search", return_value=None)
    mocker.patch("routers.search.semantic_search", return_value=mock_chunks)
    mocker.patch("routers.search.synthesise_answer", return_value="Valid Answer")
    mocker.patch("routers.search.cache_search_result", side_effect=Exception("Redis down"))

    res = await async_client.post(
        "/search",
        json={"query": "test query"},
        headers=auth_headers
    )
    
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "Valid Answer"
    assert data["cached"] is False
