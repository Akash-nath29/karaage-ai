import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Question(Base):
    """Question bank entry (PRD H1–H2). Extracted questions start as drafts for review (H3); generated and
    hand-written ones are approved. The unit comes from the topic."""

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), index=True)
    text: Mapped[str] = mapped_column(Text)
    # mcq | true_false | fill_blank | numerical | short | long | descriptive
    type: Mapped[str] = mapped_column(String(20))
    marks: Mapped[int]
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")  # easy | medium | hard
    options: Mapped[list[str]] = mapped_column(JSONB, default=list)  # mcq / true_false
    # Answer key: option index (mcq, true_false), number (numerical), "a|b" accepted words (fill_blank),
    # or a model answer (short, long, descriptive). None until written (extracted papers have no answers).
    answer: Mapped[str | None] = mapped_column(Text)
    rubric: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)  # [{criterion, marks}] for written answers
    explanation: Mapped[str] = mapped_column(Text, default="")
    source_kind: Mapped[str] = mapped_column(String(20))  # extracted | generated | manual
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), index=True)
    source_page: Mapped[int | None]
    source_label: Mapped[str] = mapped_column(String(50), default="")  # "Q3(b)" in the paper
    status: Mapped[str] = mapped_column(String(10), default="approved")  # draft | approved
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())


class Quiz(Base):
    """Private to whoever made it, with its attempts (A21, §4.3). The questions come from the shared bank."""

    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)  # scope and filters it was built with (H4)
    status: Mapped[str] = mapped_column(String(20), default="generating")  # generating | ready | failed
    job_id: Mapped[uuid.UUID | None]
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int]


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="grading")  # grading | graded | failed
    score: Mapped[float] = mapped_column(default=0)
    max_score: Mapped[float] = mapped_column(default=0)
    job_id: Mapped[uuid.UUID | None]
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())
    graded_at: Mapped[datetime | None]


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    position: Mapped[int]
    answer: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float | None]  # None until graded
    max_score: Mapped[float]
    graded_by: Mapped[str | None] = mapped_column(String(10))  # auto (deterministic, H5) | ai (rubric, estimated)
    # ai: {criteria: [{criterion, marks, awarded}], correct_concepts, missing_concepts, incorrect_statements, suggestions}
    feedback: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
