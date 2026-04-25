import hashlib
import json
import logging
from uuid import UUID
from upstash_redis import Redis

from core.config import settings

logger = logging.getLogger(__name__)

# Initialize the Upstash Redis REST client
# Note: This uses HTTP underneath, so it is serverless-friendly and avoids connection limits.
redis = Redis(
    url=settings.UPSTASH_REDIS_REST_URL,
    token=settings.UPSTASH_REDIS_REST_TOKEN
)

async def get_cached_search(user_id: UUID, query: str) -> dict | None:
    """
    Attempts to retrieve a cached search result from Upstash Redis.
    Failures are completely silent to ensure high availability.
    """
    try:
        # Create a deterministic cache key using an MD5 hash of the normalized query
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        cache_key = f"search:{user_id}:{query_hash}"
        
        # Upstash REST client is synchronous but extremely fast (<50ms).
        value = redis.get(cache_key)
        
        if value:
            # Upstash might return parsed JSON or a raw string depending on how it was stored
            if isinstance(value, str):
                return json.loads(value)
            return value
    except Exception as e:
        logger.warning(f"Cache read failed for user {user_id}: {e}")
        
    return None

async def cache_search_result(user_id: UUID, query: str, result: dict, ttl_seconds: int = 3600):
    """
    Caches a search result in Upstash Redis.
    Failures are completely silent.
    """
    try:
        query_hash = hashlib.md5(query.lower().strip().encode()).hexdigest()
        cache_key = f"search:{user_id}:{query_hash}"
        
        # Serialize with default=str to safely handle UUIDs and dates
        serialized_result = json.dumps(result, default=str)
        
        # Save to Redis with an expiration (Time-to-Live)
        redis.set(cache_key, serialized_result, ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"Cache write failed for user {user_id}: {e}")