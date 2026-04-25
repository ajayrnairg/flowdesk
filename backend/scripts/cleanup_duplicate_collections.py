import asyncio
import os
import sys

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, text
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from models.knowledge import Collection

async def cleanup():
    print("Searching for duplicate collections...")
    
    async with AsyncSessionLocal() as db:
        # Find duplicates: same user_id and name
        # We keep the oldest one (min created_at or min id)
        
        # This query finds the IDs of collections that are NOT the oldest for their (user_id, name) group
        stmt = text("""
            DELETE FROM collections
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (PARTITION BY user_id, name ORDER BY created_at ASC) as row_num
                    FROM collections
                ) t
                WHERE t.row_num > 1
            )
        """)
        
        result = await db.execute(stmt)
        await db.commit()
        print(f"Cleanup complete. Removed duplicate collections.")

if __name__ == "__main__":
    asyncio.run(cleanup())
