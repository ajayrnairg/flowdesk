import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase, mapped_column
from sqlalchemy import select, delete, String, Boolean, Date, Text, Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import enum

class Base(DeclarativeBase):
    pass

class TaskScope(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"

class TaskPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Task(Base):
    __tablename__ = "tasks"
    id = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id = mapped_column(PG_UUID(as_uuid=True))
    title = mapped_column(String(255))
    notes = mapped_column(Text)
    scope = mapped_column(Enum(TaskScope, native_enum=False))
    priority = mapped_column(Enum(TaskPriority, native_enum=False))
    due_date = mapped_column(Date)
    is_done = mapped_column(Boolean)
    is_recurring = mapped_column(Boolean)
    parent_id = mapped_column(PG_UUID(as_uuid=True))

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_eKX0faI8JZnk@ep-restless-bar-a1t2tsxw-pooler.ap-southeast-1.aws.neon.tech/flowdesk?ssl=require"

async def cleanup():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Delete all tasks with "DSA" in the title to let user start fresh
        stmt = delete(Task).where(Task.title.ilike('%DSA%'))
        result = await session.execute(stmt)
        await session.commit()
        print(f"Deleted tasks related to DSA.")

if __name__ == "__main__":
    asyncio.run(cleanup())
