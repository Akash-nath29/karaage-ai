import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    code: str = Field(default="", max_length=50)
    term: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=2000)


class CourseUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=50)
    term: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    code: str
    term: str
    description: str
    created_at: datetime
