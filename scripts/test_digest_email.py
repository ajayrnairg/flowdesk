import asyncio
import os
import sys
from pathlib import Path

# Add the backend directory to sys.path so we can import models and services
backend_path = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_path))

# Load environment variables manually
from dotenv import load_dotenv
load_dotenv(str(backend_path / ".env"))

# Import all models to ensure they are registered with SQLAlchemy
from models.user import User
from models.task import Task
from models.knowledge import KnowledgeItem, Collection, CollectionItem
from models.notification import NotificationLog, PushSubscription

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from core.config import settings
from services.digest_query import build_digest_for_user, get_suggested_reading
from services.email_service import send_digest_email

async def test_digest():
    # 1. Connect to the real database
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 2. Fetch the first user
        stmt = select(User).order_by(User.created_at.asc())
        result = await db.execute(stmt)
        user = result.scalars().first()

        if not user:
            print("No users found in database.")
            return

        print(f"Testing digest for user: {user.email} (ID: {user.id})")

        # 3. Call build_digest_for_user
        print("\n--- Building Digest Data ---")
        digest_data = await build_digest_for_user(user.id, db)
        print(f"Daily tasks: {len(digest_data.get('daily_tasks', []))}")
        print(f"Weekly tasks: {len(digest_data.get('weekly_tasks', []))}")
        print(f"Monthly tasks: {len(digest_data.get('monthly_tasks', []))}")

        # 4. Call get_suggested_reading
        print("\n--- Fetching Suggested Reading ---")
        suggested_reading = await get_suggested_reading(user.id, db)
        for item in suggested_reading:
            print(f"- [{item['content_type']}] {item['title']} (from {item['collection_name']})")

        # 5. Call send_digest_email using real Resend API
        print("\n--- Sending Real Email via Resend ---")
        success = await send_digest_email(user, digest_data, suggested_reading)

        if success:
            print("\n✅ Digest sent successfully! Check your inbox.")
        else:
            print("\n❌ Failed to send digest email.")

if __name__ == "__main__":
    asyncio.run(test_digest())
