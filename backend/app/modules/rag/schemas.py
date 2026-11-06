import uuid

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=1000)
    course_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)  # search only these documents
    top_k: int | None = Field(default=None, ge=1, le=20)


class Passage(BaseModel):
    """A retrieved passage with everything needed to cite it (PRD D7)."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page_start: int | None
    page_end: int | None
    heading_path: str
    content: str
    content_type: str
    score: float
