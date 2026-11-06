import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentKind = Literal["syllabus", "textbook", "notes", "question_paper", "other"]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    course_id: uuid.UUID | None
    kind: str
    filename: str
    file_type: str
    size_bytes: int
    status: str
    error: str | None
    page_count: int | None
    chunk_count: int
    job_id: uuid.UUID | None
    uploaded_by: uuid.UUID | None
    created_at: datetime
    processed_at: datetime | None


class DocumentUpdate(BaseModel):
    kind: DocumentKind | None = None
    course_id: uuid.UUID | None = None  # send null to unassign; omit to leave unchanged


class DocumentStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    error: str | None
    job_id: uuid.UUID | None
