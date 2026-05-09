from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from core.config import settings

# Auto-fix DATABASE_URL for Render/Neon if it's missing the +asyncpg driver
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Use NullPool for serverless/Neon:
#   - No persistent connection pool = zero idle connections on Neon
#   - Connections are opened per-request and closed immediately after
#   - pool_pre_ping is irrelevant (and removed) since there's no pool to ping
#   - This is the recommended approach for Neon + serverless runtimes
engine_kwargs: dict = {
    "echo": False,
    "poolclass": NullPool,
}

# Disable prepared statement cache for Neon/PgBouncer transaction pooling
if "postgresql" in db_url:
    engine_kwargs["connect_args"] = {"statement_cache_size": 0}

engine = create_async_engine(db_url, **engine_kwargs)

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents attributes from expiring after commit, crucial for async
)

# Base class for SQLAlchemy models (SQLAlchemy 2.0 style)
class Base(DeclarativeBase):
    pass

# Dependency to get DB session in FastAPI routes
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()