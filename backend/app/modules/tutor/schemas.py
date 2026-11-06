import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["learn", "doubt", "socratic", "exam", "revision"]


class SessionIn(BaseModel):
    """Context is optional: a lesson implies its topic, a topic its course, a course its workspace."""

    workspace_id: uuid.UUID | None = None
    course_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    mode: Mode = "doubt"
    title: str | None = Field(default=None, max_length=200)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    course_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    lesson_id: uuid.UUID | None
    mode: Mode
    title: str
    created_at: datetime
    updated_at: datetime
    course_title: str | None = None
    topic_title: str | None = None


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    mode: Mode | None = None  # switches the session's mode from this message on
    web: bool = False  # also search the web now (one Tavily search, counted in the budget)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    mode: str
    content: str
    citations: list[dict[str, Any]]
    suggestions: list[str]
    status: str
    model: str | None
    created_at: datetime
