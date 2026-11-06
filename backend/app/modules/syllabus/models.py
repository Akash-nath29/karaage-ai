import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.ai.providers.base import EMBEDDING_DIM
from app.database.session import Base


class Syllabus(Base):
    """One per course (A10). `draft` is the latest parse (editable until confirmed); `confirmed` is the snapshot
    that built the course's units and topics. Re-parsing never touches the confirmed structure."""

    __tablename__ = "syllabi"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), unique=True)
    # The original upload stays available as a document (PRD C3); SET NULL if the user deletes it.
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="parsing")  # parsing | draft | confirmed | failed
    job_id: Mapped[uuid.UUID | None]
    error: Mapped[str | None] = mapped_column(Text)
    page_start: Mapped[int | None]
    page_end: Mapped[int | None]
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confirmed: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    confirmed_at: Mapped[datetime | None]


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    hours: Mapped[int | None]
    ordinal: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Topic(Base):
    """A top-level topic (lessons attach here, A2) or a subtopic (parent_id set)."""

    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    ordinal: Mapped[int]
    # Cached embedding of the topic's description, for mapping chunks to topics (re-embedded when it changes).
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DocumentTopic(Base):
    """A document the student pinned to a topic (C4 manual mapping, D12): its passages are always offered as
    evidence when that topic's lesson is generated, on top of the automatic chunk → topic matches."""

    __tablename__ = "document_topics"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
