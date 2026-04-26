import pytest
from httpx import AsyncClient

# Reusable Data for Testing
REGISTER_PAYLOAD = {
    "email": "test@example.com",
    "password": "strongpassword123",
    "timezone": "UTC"
}

LOGIN_PAYLOAD = {
    "email": "test@example.com",
    "password": "strongpassword123"
}

# 1. POST /auth/register
@pytest.mark.asyncio
async def test_register_happy_path(async_client: AsyncClient):
    response = await async_client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data
    assert "hashed_password" not in data
    assert "id" in data

@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    # First successful registration
    await async_client.post("/auth/register", json=REGISTER_PAYLOAD)
    
    # Try it again - Should reject 400
    response = await async_client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


# 2. POST /auth/login
@pytest.mark.asyncio
async def test_login_correct_credentials(async_client: AsyncClient):
    # Setup the user
    await async_client.post("/auth/register", json=REGISTER_PAYLOAD)

    # Login safely
    response = await async_client.post("/auth/login", json=LOGIN_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    # Setup the user
    await async_client.post("/auth/register", json=REGISTER_PAYLOAD)

    # Try bad password
    wrong_login = {
        "email": "test@example.com",
        "password": "WRONG_PASSWORD"
    }
    response = await async_client.post("/auth/login", json=wrong_login)
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


# 3. GET /auth/me
@pytest.mark.asyncio
async def test_read_users_me_valid_token(authenticated_client, test_user: User):
    # Use the authenticated_client fixture which handles the Clerk override
    client = await authenticated_client(test_user)
    
    me_response = await client.get("/auth/me")
    assert me_response.status_code == 200
    
    me_data = me_response.json()
    assert me_data["email"] == "test@example.com"
    assert "id" in me_data

@pytest.mark.asyncio
async def test_read_users_me_unauthorized(async_client: AsyncClient):
    # No Auth Header included
    response = await async_client.get("/auth/me")
    assert response.status_code == 401
    # Depending on whether it's FastAPI or our custom catch, the detail might vary.
    # If the header is missing, FastAPI returns "Not authenticated".
    assert response.json()["detail"] in ["Not authenticated", "Invalid or expired token"]
