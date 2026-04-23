import asyncio
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient

# Fixture to provide auth headers for user A
@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient) -> dict:
    email = "user_a_knowledge@example.com"
    password = "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# Fixture to provide auth headers for user B
@pytest_asyncio.fixture
async def auth_headers_b(async_client: AsyncClient) -> dict:
    email = "user_b_knowledge@example.com"
    password = "password123"
    await async_client.post("/auth/register", json={"email": email, "password": password})
    res = await async_client.post("/auth/login", json={"email": email, "password": password})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

from tests.conftest import TestingSessionLocal

@pytest_asyncio.fixture(autouse=True)
def patch_bg_db(mocker):
    # Patch AsyncSessionLocal in the router so background tasks use the test DB
    mocker.patch("routers.knowledge.AsyncSessionLocal", new=TestingSessionLocal)

# Helper to wait for background tasks in ASGITransport
# (Though ASGITransport usually runs them after the response, 
# a slight delay ensures DB commits are fully visible.)
async def wait_for_bg():
    await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_save_article_url(async_client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch(
        "services.ingestion_orchestrator.fetch_with_jina",
        return_value={"title": "Test Article", "raw_text": "Some content about Python", "cover_image_url": None}
    )
    mocker.patch(
        "services.ingestion_orchestrator.generate_summary",
        return_value="Great article about Python."
    )

    res = await async_client.post(
        "/knowledge", 
        json={"url": "https://example.com/python-article"}, 
        headers=auth_headers
    )
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await async_client.get(f"/knowledge/{item_id}", headers=auth_headers)
    assert res_get.status_code == 200
    data = res_get.json()
    
    assert data["status"] == "done"
    assert data["summary"] == "Great article about Python."
    assert data["title"] == "Test Article"
    assert data["content_type"] == "article"

@pytest.mark.asyncio
async def test_save_youtube_url(async_client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch(
        "services.ingestion_orchestrator.fetch_youtube_content",
        return_value={"title": "Python Tutorial", "raw_text": "Welcome to this tutorial...", "cover_image_url": "http://img.jpg"}
    )
    mocker.patch(
        "services.ingestion_orchestrator.generate_summary",
        return_value="Great video."
    )

    res = await async_client.post(
        "/knowledge", 
        json={"url": "https://youtube.com/watch?v=abc123"}, 
        headers=auth_headers
    )
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await async_client.get(f"/knowledge/{item_id}", headers=auth_headers)
    assert res_get.status_code == 200
    data = res_get.json()
    
    assert data["content_type"] == "youtube"
    assert data["title"] == "Python Tutorial"
    assert data["status"] == "done"

@pytest.mark.asyncio
async def test_twitter_url_returns_use_bookmarklet(async_client: AsyncClient, auth_headers: dict):
    res = await async_client.post(
        "/knowledge", 
        json={"url": "https://twitter.com/user/status/123"}, 
        headers=auth_headers
    )
    # The route returns HTTP 202, but with a special dictionary instead of the standard accepted format
    assert res.status_code == 202
    assert res.json().get("status") == "use_bookmarklet"

@pytest.mark.asyncio
async def test_bookmarklet_save(async_client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch(
        "services.ingestion_orchestrator.generate_summary",
        return_value="Bookmarklet summary."
    )
    
    payload = {
        "url": "https://twitter.com/user/status/123",
        "page_title": "A tweet",
        "selected_text": "This is a great tweet",
        "content_type": "twitter"
    }
    res = await async_client.post("/knowledge/bookmarklet", json=payload, headers=auth_headers)
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await async_client.get(f"/knowledge/{item_id}", headers=auth_headers)
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["content_type"] == "twitter"
    assert data["raw_text"] == "This is a great tweet"
    assert data["title"] == "A tweet"

@pytest.mark.asyncio
async def test_pdf_upload(async_client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch(
        "routers.knowledge.extract_pdf_text",
        return_value={"title": "Test PDF", "raw_text": "PDF Content"}
    )
    mocker.patch(
        "services.ingestion_orchestrator.generate_summary",
        return_value="PDF Summary"
    )
    
    # Minimal valid PDF bytes (dummy content)
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
    res = await async_client.post("/knowledge/upload-pdf", files=files, headers=auth_headers)
    
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await async_client.get(f"/knowledge/{item_id}", headers=auth_headers)
    assert res_get.status_code == 200
    data = res_get.json()
    
    assert data["content_type"] == "pdf"
    assert data["title"] == "Test PDF"

@pytest.mark.asyncio
async def test_pdf_too_large(async_client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch(
        "routers.knowledge.extract_pdf_text",
        return_value={"error": "file_too_large"}
    )
    
    pdf_bytes = b"dummy"
    files = {"file": ("large.pdf", pdf_bytes, "application/pdf")}
    res = await async_client.post("/knowledge/upload-pdf", files=files, headers=auth_headers)
    
    assert res.status_code == 413

@pytest.mark.asyncio
async def test_ownership(async_client: AsyncClient, auth_headers: dict, auth_headers_b: dict, mocker):
    mocker.patch("services.ingestion_orchestrator.fetch_with_jina", return_value={"title": "A", "raw_text": "A"})
    mocker.patch("services.ingestion_orchestrator.generate_summary", return_value="A")

    res = await async_client.post(
        "/knowledge", 
        json={"url": "https://example.com/a"}, 
        headers=auth_headers
    )
    item_id = res.json()["id"]
    await wait_for_bg()

    # User B tries to GET
    res_get = await async_client.get(f"/knowledge/{item_id}", headers=auth_headers_b)
    assert res_get.status_code == 403

    # User B tries to DELETE
    res_del = await async_client.delete(f"/knowledge/{item_id}", headers=auth_headers_b)
    assert res_del.status_code == 403

    # User A GET and DELETE should succeed
    assert (await async_client.get(f"/knowledge/{item_id}", headers=auth_headers)).status_code == 200
    assert (await async_client.delete(f"/knowledge/{item_id}", headers=auth_headers)).status_code == 204

@pytest.mark.asyncio
async def test_filter_by_content_type(async_client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch("services.ingestion_orchestrator.fetch_with_jina", return_value={"title": "Article", "raw_text": "A"})
    mocker.patch("services.ingestion_orchestrator.fetch_youtube_content", return_value={"title": "Video", "raw_text": "V"})
    mocker.patch("services.ingestion_orchestrator.generate_summary", return_value="Sum")

    # Create Article
    await async_client.post("/knowledge", json={"url": "https://example.com/a"}, headers=auth_headers)
    # Create YouTube
    await async_client.post("/knowledge", json={"url": "https://youtube.com/watch?v=123"}, headers=auth_headers)
    
    await wait_for_bg()

    # Filter by youtube
    res_get = await async_client.get("/knowledge?content_type=youtube", headers=auth_headers)
    assert res_get.status_code == 200
    items = res_get.json()
    assert len(items) == 1
    assert items[0]["content_type"] == "youtube"

@pytest.mark.asyncio
async def test_failed_extraction(async_client: AsyncClient, auth_headers: dict, mocker):
    mocker.patch(
        "services.ingestion_orchestrator.fetch_with_jina",
        return_value={"error": "timeout"}
    )

    res = await async_client.post(
        "/knowledge", 
        json={"url": "https://example.com/fail"}, 
        headers=auth_headers
    )
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await async_client.get(f"/knowledge/{item_id}", headers=auth_headers)
    assert res_get.status_code == 200
    data = res_get.json()
    
    assert data["status"] == "failed"
