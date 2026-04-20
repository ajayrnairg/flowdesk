from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

# Initialize async engine for NeonDB.
# pool_pre_ping checks connections before using them (handles serverless connection drops).
# pool_recycle reconnects connections older than 300s to avoid DB timeouts.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for debugging SQL queries
    pool_pre_ping=True,
    pool_recycle=300,
)

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False, # Prevents attributes from expiring after commit, crucial for async
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