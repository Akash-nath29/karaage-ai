import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Claim(BaseModel):
    claim: str
    status: str  # verified | unverified | disputed
    sources: list[uuid.UUID]  # web sources (research_sources ids)
    materials: list[uuid.UUID]  # the student's uploaded material (document_chunks ids)
    contradicting: list[uuid.UUID]


class ResearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    job_id: uuid.UUID | None
    status: str
    error: str | None
    sufficient: bool | None
    covered: list[str]
    missing: list[str]
    queries: list[str]
    claims: list[Claim]
    source_count: int
    model: str | None
    prompt_version: str | None
    created_at: datetime
    finished_at: datetime | None


class ResearchSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    title: str
    domain: str
    source_type: str
    quality: float
    relevance: float
    published_date: str | None
    retrieved_at: datetime
    content_kind: str
    passages: list[str]
    verification_status: str


class ResearchRequest(BaseModel):
    refresh: bool = False  # ignore a recent result and search again
