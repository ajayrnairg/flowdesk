import uuid
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock
from models.user import User
from models.knowledge import KnowledgeItem, ItemStatus
from tests.conftest import TestingSessionLocal

@pytest.mark.asyncio
async def test_semantic_search_returns_answer(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    item_id = uuid.uuid4()
    async with TestingSessionLocal() as db:
        item = KnowledgeItem(
            id=item_id,
            user_id=test_user.id,
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
    res = await client.post(
        "/search",
        json={"query": "test query"}
    )
    
    # Assert
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "This is the synthesised answer."
    assert len(data["sources"]) == 2
    assert data["cached"] is False
    assert isinstance(data["took_ms"], int) and data["took_ms"] >= 0

@pytest.mark.asyncio
async def test_cache_hit_returns_cached_result(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
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
    }
    
    mocker.patch("routers.search.get_cached_search", return_value=cached_response)
    mock_semantic_search = mocker.patch("routers.search.semantic_search")

    res = await client.post(
        "/search",
        json={"query": "cached query"}
    )
    
    assert res.status_code == 200
    data = res.json()
    assert data["cached"] is True
    assert data["answer"] == "Cached answer."
    mock_semantic_search.assert_not_called()

@pytest.mark.asyncio
async def test_empty_knowledge_base_returns_graceful_message(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    mocker.patch("routers.search.get_cached_search", return_value=None)
    mocker.patch("routers.search.semantic_search", return_value=[])
    mocker.patch("routers.search.synthesise_answer", return_value="I could not find relevant information in your knowledge base for this query.")
    
    res = await client.post(
        "/search",
        json={"query": "no matches"}
    )
    
    assert res.status_code == 200
    assert "could not find relevant" in res.json()["answer"]

@pytest.mark.asyncio
async def test_query_too_short_returns_422(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    res = await client.post(
        "/search",
        json={"query": "a"}
    )
    assert res.status_code == 422

@pytest.mark.asyncio
async def test_reindex_endpoint(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    item_id = uuid.uuid4()
    async with TestingSessionLocal() as db:
        item = KnowledgeItem(
            id=item_id,
            user_id=test_user.id,
            content_type="article",
            status=ItemStatus.DONE.value
        )
        db.add(item)
        await db.commit()

    mocker.patch("routers.search.index_knowledge_item", new_callable=AsyncMock)

    res = await client.get(f"/search/reindex/{item_id}")
    assert res.status_code == 200
    assert res.json() == {"status": "reindexed", "item_id": str(item_id)}

@pytest.mark.asyncio
async def test_reindex_other_user_item(authenticated_client, test_user: User, test_user_b: User, mocker):
    client_b = await authenticated_client(test_user_b)
    item_id = uuid.uuid4()
    async with TestingSessionLocal() as db:
        # Create item owned by user A
        item = KnowledgeItem(
            id=item_id,
            user_id=test_user.id,
            content_type="article",
            status=ItemStatus.DONE.value
        )
        db.add(item)
        await db.commit()

    mocker.patch("routers.search.index_knowledge_item", return_value=None)

    # User B tries to reindex it
    res = await client_b.get(f"/search/reindex/{item_id}")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_similarity_score_is_between_0_and_1(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
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

    res = await client.post(
        "/search",
        json={"query": "test query"}
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
async def test_cache_write_failure_does_not_break_search(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
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

    res = await client.post(
        "/search",
        json={"query": "test query"}
    )
    
    assert res.status_code == 200
    data = res.json()
    assert data["answer"] == "Valid Answer"
    assert data["cached"] is False
