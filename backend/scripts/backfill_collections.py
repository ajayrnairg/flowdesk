import asyncio
import os
import sys

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.future import select
from sqlalchemy import outerjoin

from core.database import AsyncSessionLocal
from models.user import User
from models.knowledge import KnowledgeItem, CollectionItem
from models.task import Task
from models.notification import NotificationLog, PushSubscription
from services.auto_collection_service import auto_add_to_collection

async def backfill():
    print("Starting backfill of collections...")
    
    async with AsyncSessionLocal() as db:
        # 1. Query KnowledgeItems that have NO CollectionItem rows
        # We use a LEFT OUTER JOIN and filter where the join-side ID is NULL
        stmt = (
            select(KnowledgeItem)
            .select_from(outerjoin(KnowledgeItem, CollectionItem, KnowledgeItem.id == CollectionItem.knowledge_item_id))
            .where(CollectionItem.id == None)
        )
        
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        count = 0
        for item in items:
            # 2. Call auto_add_to_collection
            # The service handles get_or_create logic internally
            await auto_add_to_collection(
                knowledge_item_id=item.id,
                user_id=item.user_id,
                content_type=item.content_type,
                db=db
            )
            print(f"Added item '{item.title}' to its auto-collection")
            count += 1
            
        await db.commit()
        print(f"\nBackfilled {count} items into collections")

if __name__ == "__main__":
    asyncio.run(backfill())
