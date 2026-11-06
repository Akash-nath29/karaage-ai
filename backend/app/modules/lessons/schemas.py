import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.lessons.document import Depth


class GenerateRequest(BaseModel):
    depth: Depth | None = None  # default: LESSON_DEFAULT_DEPTH
    # default: shared for editors and above, private for viewers (who can only make private lessons, D28)
    visibility: Literal["workspace", "private"] | None = None


class EnrichRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    request: str = Field(min_length=3, max_length=500)  # e.g. "another worked example with numbers"


class FeedbackIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    rating: Literal[1, -1]
    comment: str = Field(default="", max_length=2000)


class PinIn(BaseModel):
    document_ids: list[uuid.UUID] = Field(max_length=20)


class PinnedDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    kind: str


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic_id: uuid.UUID
    course_id: uuid.UUID
    depth: str
    visibility: str  # workspace | private
    owner_id: uuid.UUID | None
    status: str  # queued | generating | ready | failed | cancelled
    job_id: uuid.UUID | None
    error: str | None
    current_version: int  # 0 = nothing to read yet
    outdated_reason: str | None
    created_at: datetime


class VersionMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    version: int
    kind: str  # generated | enriched
    model: str
    prompt_version: str
    warnings: list[str]
    input_tokens: int
    output_tokens: int
    created_at: datetime


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    kind: str  # material | web
    document_id: uuid.UUID | None
    filename: str | None
    page_start: int | None
    page_end: int | None
    heading_path: str | None
    url: str | None
    title: str | None
    domain: str | None
    quote: str
    available: bool = True  # False once the cited document was deleted (the quote snapshot remains)


class LessonDetail(BaseModel):
    lesson: LessonOut
    workspace_id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    unit_title: str
    topic_title: str
    version: VersionMeta
    document: dict[str, Any]  # LessonDocument (app/modules/lessons/document.py)
    citations: list[CitationOut]


class LessonListItem(LessonOut):
    """A lesson in a workspace overview (shared learning resources)."""

    course_title: str
    topic_title: str
    updated_at: datetime | None  # when the current version was made


class BatchResult(BaseModel):
    count: int
