from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class BookmarkletPayload(BaseModel):
    url: str
    selected_text: str
    page_title: str
    content_type: str
    collection_id: Optional[UUID] = None