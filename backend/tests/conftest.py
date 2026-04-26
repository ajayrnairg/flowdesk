import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Import the actual models and app
from main import app
from core.database import get_db
from models.user import Base, User
import models.task     
import models.notification  # register NotificationLog + PushSubscription with Base.metadata
from core.config import settings
from core.clerk_auth import get_current_user

# Calculate a separate test database URL
# ... (rest of the URL calculation logic) ...
original_url = settings.DATABASE_URL

if "sqlite" in original_url:
    TEST_SQLALCHEMY_DATABASE_URL = original_url
else:
    TEST_SQLALCHEMY_DATABASE_URL = original_url.replace("/flowdesk", "/flowdesk_test")

engine_test = create_async_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
)
TestingSessionLocal = async_sessionmaker(
    bind=engine_test, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

@pytest_asyncio.fixture(scope="session")
async def engine():
    yield engine_test

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    yield
    async with engine_test.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'DELETE FROM "{table.name}";'))

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

# Helper to create a user in the test DB
async def create_test_user(db: AsyncSession, email: str, clerk_id: str = None) -> User:
    clerk_id = clerk_id or f"user_{email.split('@')[0]}"
    user = User(
        email=email,
        hashed_password="",
        clerk_user_id=clerk_id,
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

# Fixture that provides an authenticated client by overriding get_current_user
@pytest_asyncio.fixture
async def authenticated_client(async_client, setup_test_db):
    """
    Returns a factory function that creates an authenticated client for a given user.
    Usage: client = await authenticated_client(some_user)
    """
    class AuthenticatedClient:
        def __init__(self, user):
            self.user = user
        
        async def _request(self, method, *args, **kwargs):
            app.dependency_overrides[get_current_user] = lambda: self.user
            return await getattr(async_client, method)(*args, **kwargs)
        
        async def get(self, *args, **kwargs): return await self._request("get", *args, **kwargs)
        async def post(self, *args, **kwargs): return await self._request("post", *args, **kwargs)
        async def patch(self, *args, **kwargs): return await self._request("patch", *args, **kwargs)
        async def delete(self, *args, **kwargs): return await self._request("delete", *args, **kwargs)
        async def put(self, *args, **kwargs): return await self._request("put", *args, **kwargs)

    async def _authenticate(user: User):
        return AuthenticatedClient(user)
    
    yield _authenticate
    # Clean up the override after the test
    if get_current_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_user]

@pytest_asyncio.fixture
async def test_user(engine):
    """Fixture to provide a standard test user."""
    async with TestingSessionLocal() as db:
        return await create_test_user(db, "test@example.com")

@pytest_asyncio.fixture
async def test_user_b(engine):
    """Fixture to provide a second test user."""
    async with TestingSessionLocal() as db:
        return await create_test_user(db, "user_b@example.com")

