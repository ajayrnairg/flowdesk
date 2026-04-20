import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from core.config import settings
from sqlalchemy import text
from models.user import Base
import models.task

async def wipe():
    engine = create_async_engine(settings.DATABASE_URL.replace('/flowdesk', '/flowdesk_test'))
    async with engine.begin() as conn:
        await conn.execute(text('DROP SCHEMA IF EXISTS public CASCADE'))
        await conn.execute(text('CREATE SCHEMA public'))
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(wipe())
