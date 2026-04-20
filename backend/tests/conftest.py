import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Import the actual models and app
from main import app
from core.database import get_db
from models.user import Base
import models.task     
import models.notification  # register NotificationLog + PushSubscription with Base.metadata
from core.config import settings

# Calculate a separate test database URL
original_url = settings.DATABASE_URL

if "sqlite" in original_url:
    # Use the SQLite memory DB directly (the /flowdesk split doesn't apply)
    TEST_SQLALCHEMY_DATABASE_URL = original_url
else:
    # PostgreSQL transformation: replace /flowdesk with /flowdesk_test
    # Note: Ensure your local Postgres / NeonDB has a "flowdesk_test" DB created!
    TEST_SQLALCHEMY_DATABASE_URL = original_url.replace("/flowdesk", "/flowdesk_test")

# Create test engine and sessionmaker
# StaticPool is REQUIRED for in-memory SQLite to share the connection across tests
engine_test = create_async_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    poolclass=StaticPool
)
TestingSessionLocal = async_sessionmaker(
    bind=engine_test, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

# conftest.py — replace the event_loop fixture and init_test_db with this

@pytest_asyncio.fixture(scope="session")
async def engine():
    """Session-scoped engine fixture."""
    yield engine_test
    # Note: we don't dispose engine_test here as it's a global, 
    # but the fixture matches the signature.

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables(engine):
    """Create schema once per session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def override_get_db():
    """Override the FastAPI dependency to use the test database"""
    async with TestingSessionLocal() as session:
        yield session

# Apply the override across the entire application testing
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Clear data out of tables per-test using DELETE FROM."""
    yield # Test runs here
    
    # Clean up after test finishes
    async with engine_test.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            # DELETE FROM is safer across different DB engines than TRUNCATE
            await conn.execute(text(f'DELETE FROM "{table.name}";'))

@pytest_asyncio.fixture
async def async_client():
    """Yield an AsyncClient for FastAPI endpoint testing bypassing network."""
    transport = ASGITransport(app=app)
    # the base_url is arbitrary, 'http://test' is a common dummy domain
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
