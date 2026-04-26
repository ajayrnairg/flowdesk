import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient
from models.user import User
from tests.conftest import TestingSessionLocal

@pytest_asyncio.fixture(autouse=True)
def patch_bg_db(mocker):
    # Patch AsyncSessionLocal in the router so background tasks use the test DB
    mocker.patch("routers.knowledge.AsyncSessionLocal", new=TestingSessionLocal)

# Helper to wait for background tasks in ASGITransport
async def wait_for_bg():
    await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_save_article_url(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    mocker.patch(
        "services.ingestion_orchestrator.fetch_with_jina",
        return_value={"title": "Test Article", "raw_text": "Some content about Python", "cover_image_url": None}
    )
    mocker.patch(
        "services.ingestion_orchestrator.generate_summary",
        return_value="Great article about Python."
    )

    res = await client.post(
        "/knowledge", 
        json={"url": "https://example.com/python-article"}
    )
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await client.get(f"/knowledge/{item_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    
    assert data["status"] == "done"
    assert data["summary"] == "Great article about Python."
    assert data["title"] == "Test Article"
    assert data["content_type"] == "article"

@pytest.mark.asyncio
async def test_save_youtube_url(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    mocker.patch(
        "services.ingestion_orchestrator.fetch_youtube_content",
        return_value={"title": "Python Tutorial", "raw_text": "Welcome to this tutorial...", "cover_image_url": "http://img.jpg"}
    )
    mocker.patch(
        "services.ingestion_orchestrator.generate_summary",
        return_value="Great video."
    )

    res = await client.post(
        "/knowledge", 
        json={"url": "https://youtube.com/watch?v=abc123"}
    )
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await client.get(f"/knowledge/{item_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    
    assert data["content_type"] == "youtube"
    assert data["title"] == "Python Tutorial"
    assert data["status"] == "done"

@pytest.mark.asyncio
async def test_twitter_url_returns_use_bookmarklet(authenticated_client, test_user: User):
    client = await authenticated_client(test_user)
    res = await client.post(
        "/knowledge", 
        json={"url": "https://twitter.com/user/status/123"}
    )
    assert res.status_code == 202
    assert res.json().get("status") == "use_bookmarklet"

@pytest.mark.asyncio
async def test_bookmarklet_save(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
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
    res = await client.post("/knowledge/bookmarklet", json=payload)
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await client.get(f"/knowledge/{item_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["content_type"] == "twitter"
    assert data["raw_text"] == "This is a great tweet"
    assert data["title"] == "A tweet"

@pytest.mark.asyncio
async def test_pdf_upload(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    mocker.patch(
        "routers.knowledge.extract_pdf_text",
        return_value={"title": "Test PDF", "raw_text": "PDF Content"}
    )
    mocker.patch(
        "services.ingestion_orchestrator.generate_summary",
        return_value="PDF Summary"
    )
    
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    files = {"file": ("test.pdf", pdf_bytes, "application/pdf")}
    res = await client.post("/knowledge/upload-pdf", files=files)
    
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await client.get(f"/knowledge/{item_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    
    assert data["content_type"] == "pdf"
    assert data["title"] == "Test PDF"

@pytest.mark.asyncio
async def test_pdf_too_large(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    mocker.patch(
        "routers.knowledge.extract_pdf_text",
        return_value={"error": "file_too_large"}
    )
    
    pdf_bytes = b"dummy"
    files = {"file": ("large.pdf", pdf_bytes, "application/pdf")}
    res = await client.post("/knowledge/upload-pdf", files=files)
    
    assert res.status_code == 413

@pytest.mark.asyncio
async def test_ownership(authenticated_client, test_user: User, test_user_b: User, mocker):
    client_a = await authenticated_client(test_user)
    client_b = await authenticated_client(test_user_b)
    
    mocker.patch("services.ingestion_orchestrator.fetch_with_jina", return_value={"title": "A", "raw_text": "A"})
    mocker.patch("services.ingestion_orchestrator.generate_summary", return_value="A")

    res = await client_a.post(
        "/knowledge", 
        json={"url": "https://example.com/a"}
    )
    item_id = res.json()["id"]
    await wait_for_bg()

    # User B tries to GET
    res_get = await client_b.get(f"/knowledge/{item_id}")
    assert res_get.status_code == 403

    # User B tries to DELETE
    res_del = await client_b.delete(f"/knowledge/{item_id}")
    assert res_del.status_code == 403

    # User A GET and DELETE should succeed
    assert (await client_a.get(f"/knowledge/{item_id}")).status_code == 200
    assert (await client_a.delete(f"/knowledge/{item_id}")).status_code == 204

@pytest.mark.asyncio
async def test_filter_by_content_type(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    mocker.patch("services.ingestion_orchestrator.fetch_with_jina", return_value={"title": "Article", "raw_text": "A"})
    mocker.patch("services.ingestion_orchestrator.fetch_youtube_content", return_value={"title": "Video", "raw_text": "V"})
    mocker.patch("services.ingestion_orchestrator.generate_summary", return_value="Sum")

    # Create Article
    await client.post("/knowledge", json={"url": "https://example.com/a"})
    # Create YouTube
    await client.post("/knowledge", json={"url": "https://youtube.com/watch?v=123"})
    
    await wait_for_bg()

    # Filter by youtube
    res_get = await client.get("/knowledge?content_type=youtube")
    assert res_get.status_code == 200
    items = res_get.json()
    assert len(items) == 1
    assert items[0]["content_type"] == "youtube"

@pytest.mark.asyncio
async def test_failed_extraction(authenticated_client, test_user: User, mocker):
    client = await authenticated_client(test_user)
    mocker.patch(
        "services.ingestion_orchestrator.fetch_with_jina",
        return_value={"error": "timeout"}
    )

    res = await client.post(
        "/knowledge", 
        json={"url": "https://example.com/fail"}
    )
    assert res.status_code == 202
    item_id = res.json()["id"]

    await wait_for_bg()

    res_get = await client.get(f"/knowledge/{item_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    
    assert data["status"] == "failed"
