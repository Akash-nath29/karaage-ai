import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class TutorSession(Base):
    """A conversation with the tutor (PRD G2), optionally about a course, topic or lesson (its context).
    Private to the person who started it (§4.3)."""

    __tablename__ = "tutor_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), index=True)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lessons.id", ondelete="SET NULL"))
    mode: Mapped[str] = mapped_column(String(20), default="doubt")  # learn | doubt | socratic | exam | revision
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())


class TutorMessage(Base):
    __tablename__ = "tutor_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tutor_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    mode: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)  # markdown; assistant text keeps [M1]/[W1] citation markers
    # [{label, kind: material|web, chunk_id, document_id, filename, page_start, page_end, url, title, domain, quote}]
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    suggestions: Mapped[list[str]] = mapped_column(JSONB, default=list)  # follow-up questions
    status: Mapped[str] = mapped_column(String(20), default="complete")  # complete | interrupted | error
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())
