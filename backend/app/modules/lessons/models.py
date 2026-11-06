import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, ForeignKey, Index, SmallInteger, String, Text, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Lesson(Base):
    """A topic's lesson at one depth: one shared with the workspace, plus at most one private lesson per person
    (D28). Content lives in versions; a lesson is never overwritten (PRD F7)."""

    __tablename__ = "lessons"
    __table_args__ = (
        Index("uq_lessons_shared", "topic_id", "depth", unique=True, postgresql_where=text("visibility = 'workspace'")),
        Index("uq_lessons_private", "topic_id", "depth", "owner_id", unique=True,
              postgresql_where=text("visibility = 'private'")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    depth: Mapped[str] = mapped_column(String(20))
    visibility: Mapped[str] = mapped_column(String(10), default="workspace")  # workspace (shared) | private
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)  # who made it
    # queued | generating | ready | failed | cancelled. "ready" with a running job = a new version is coming.
    status: Mapped[str] = mapped_column(String(20), default="queued")
    job_id: Mapped[uuid.UUID | None]
    error: Mapped[str | None] = mapped_column(Text)
    current_version: Mapped[int] = mapped_column(default=0)  # 0 = nothing generated yet
    # A source document changed or new material arrived since the current version (PRD F7).
    outdated_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


def visible_to(user_id: uuid.UUID) -> ColumnElement[bool]:
    """Shared lessons, and this user's private ones (B4)."""
    return (Lesson.visibility == "workspace") | (Lesson.owner_id == user_id)


class LessonVersion(Base):
    __tablename__ = "lesson_versions"
    __table_args__ = (UniqueConstraint("lesson_id", "version", name="uq_lesson_versions_lesson_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    version: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))  # generated | enriched
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)  # LessonDocument (document.py), schema_version inside
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    # What the lesson was built from: evidence labels → chunk/source ids and content hashes, research run.
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    document_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)  # materials used (F7 outdated check)
    warnings: Mapped[list[str]] = mapped_column(JSONB, default=list)  # dropped blocks, repaired math…
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())


class LessonCitation(Base):
    """An evidence label used in a version, with a snapshot of what it pointed to: still readable after the
    document is deleted or reprocessed (M9). kind distinguishes uploaded material from the web (PRD §11.2)."""

    __tablename__ = "lesson_citations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson_versions.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(10))  # M1… or W1…
    kind: Mapped[str] = mapped_column(String(10))  # material | web
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"))
    document_id: Mapped[uuid.UUID | None]  # snapshot (no FK): the document may be deleted later
    filename: Mapped[str | None] = mapped_column(String(255))
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    heading_path: Mapped[str | None] = mapped_column(Text)
    research_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_sources.id", ondelete="SET NULL"))
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(255))
    quote: Mapped[str] = mapped_column(Text)  # the evidence text the model saw


class LessonFeedback(Base):
    __tablename__ = "lesson_feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    version: Mapped[int]
    rating: Mapped[int] = mapped_column(SmallInteger)  # 1 helpful, -1 not helpful
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
