from uuid import UUID
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="The user's search query")

class SearchSource(BaseModel):
    knowledge_item_id: UUID
    title: str | None
    content_type: str
    url: str | None
    chunk_excerpt: str
    similarity_score: float

class SearchResponse(BaseModel):
    query: str
    answer: str
    sources: list[SearchSource]
    cached: bool
    took_ms: int