import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.rag.schemas import Passage

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


# --- Structure (Course → Units → Topics → Subtopics, A2). The same tree is used for drafts and edits. ---------
# Nodes with an id update that unit/topic; nodes without one are matched by title, else created (ids survive
# renames done through the editor; lessons and progress attach to topic ids).


class SubtopicNode(BaseModel):
    model_config = ConfigDict(extra="forbid")  # e.g. subtopics nested in a subtopic: reject, don't drop

    id: uuid.UUID | None = None
    title: Title


class TopicNode(BaseModel):
    model_config = ConfigDict(extra="forbid")  # e.g. subtopics nested in a subtopic: reject, don't drop

    id: uuid.UUID | None = None
    title: Title
    subtopics: list[SubtopicNode] = Field(default_factory=list, max_length=60)


class UnitNode(BaseModel):
    model_config = ConfigDict(extra="forbid")  # e.g. subtopics nested in a subtopic: reject, don't drop

    id: uuid.UUID | None = None
    title: Title
    hours: int | None = Field(default=None, ge=0, le=500)
    topics: list[TopicNode] = Field(default_factory=list, max_length=80)


class Structure(BaseModel):
    model_config = ConfigDict(extra="forbid")  # e.g. subtopics nested in a subtopic: reject, don't drop

    units: list[UnitNode] = Field(max_length=50)


class SyllabusDraft(Structure):
    subject_name: str = Field(default="", max_length=300)
    subject_code: str = Field(default="", max_length=100)
    exam_structure: str = Field(default="", max_length=5000)
    references: list[Annotated[str, StringConstraints(max_length=1000)]] = Field(default_factory=list, max_length=50)


class LinkSyllabus(BaseModel):
    document_id: uuid.UUID


class SyllabusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    document_id: uuid.UUID | None
    status: str
    job_id: uuid.UUID | None
    error: str | None
    page_start: int | None
    page_end: int | None
    draft: dict[str, Any] | None
    confirmed: dict[str, Any] | None
    model: str | None
    prompt_version: str | None
    confirmed_at: datetime | None
    generation_estimate: dict[str, int] | None = None  # drafts: lessons, ai_calls, tokens, web_searches_max


# --- Read models with per-topic content status (A1) and coverage (C5) -------------------------------------


class SubtopicOut(BaseModel):
    id: uuid.UUID
    title: str


class TopicOut(BaseModel):
    id: uuid.UUID
    title: str
    status: str  # not_started | materials_available | generation_pending | lesson_available (A1)
    material_count: int  # passages from the course's materials mapped to this topic
    lesson_id: uuid.UUID | None = None  # the lesson to open (default depth first)
    lesson_status: str | None = None
    subtopics: list[SubtopicOut]


class UnitOut(BaseModel):
    id: uuid.UUID
    title: str
    hours: int | None
    coverage: float  # share of topics with materials
    topics: list[TopicOut]


class StructureOut(BaseModel):
    units: list[UnitOut]
    topic_count: int
    coverage: float
    lessons_ready: int = 0
    lessons_pending: int = 0


class TopicListItem(BaseModel):
    id: uuid.UUID
    title: str
    unit_id: uuid.UUID
    parent_id: uuid.UUID | None
    ordinal: int
    status: str
    material_count: int


class TopicDetail(BaseModel):
    id: uuid.UUID
    title: str
    parent_id: uuid.UUID | None
    course_id: uuid.UUID
    course_title: str
    workspace_id: uuid.UUID
    unit_id: uuid.UUID
    unit_title: str
    status: str
    material_count: int
    subtopics: list[SubtopicOut]
    materials: list[Passage]  # passages from the course's materials mapped to this topic
