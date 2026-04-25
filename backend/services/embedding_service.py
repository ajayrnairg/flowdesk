import asyncio
import logging
from google import genai
from core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_message

logger = logging.getLogger(__name__)

# Retry strategy for Gemini API rate limits (429 errors)
gemini_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_message(match="429"),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        f"Rate limit hit (429). Retrying attempt {retry_state.attempt_number}..."
    )
)

# Initialize the SDK client globally
client = genai.Client(api_key=settings.GEMINI_API_KEY)

@gemini_retry
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generates embeddings for a batch of documents. 
    Handles Google's 100-item batch limit and free-tier rate limits.
    """
    if not texts:
        return []

    all_embeddings = []
    batch_size = 100  # API limit for text-embedding-004

    try:
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # task_type="RETRIEVAL_DOCUMENT" is critical here. It tells the model
            # that this text represents the "corpus" to be searched, optimizing
            # its vector placement to be matched against queries later.
            result = await client.aio.models.embed_content(
                model=settings.EMBEDDING_MODEL,
                contents=batch,
                config={
                    "task_type": "RETRIEVAL_DOCUMENT",
                    "output_dimensionality": 768
                }
            )
            
            for emb in result.embeddings:
                all_embeddings.append(emb.values)
            
            # Rate limit mitigation for free tier: sleep briefly between batches
            if i + batch_size < len(texts):
                await asyncio.sleep(0.5)
                
        return all_embeddings
    except Exception as e:
        logger.error(f"Failed to embed text batch: {e}")
        raise

@gemini_retry
async def embed_query(query: str) -> list[float]:
    """
    Generates an embedding for a user search query.
    """
    try:
        # task_type="RETRIEVAL_QUERY" is critical here. It tells the model to optimize
        # this vector to seek out "RETRIEVAL_DOCUMENT" vectors. Mixing these up
        # severely degrades cosine similarity quality.
        result = await client.aio.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=query,
            config={
                "task_type": "RETRIEVAL_QUERY",
                "output_dimensionality": 768
            }
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        raise