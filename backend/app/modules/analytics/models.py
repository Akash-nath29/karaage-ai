import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class TopicProgress(Base):
    """A learner's progress on one topic (PRD H6, A14), private to them (§4.3, §I "per user"). Status is derived
    when read (it depends on time: A14's 14-day rule)."""

    __tablename__ = "topic_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    studied_at: Mapped[datetime | None]
    questions_attempted: Mapped[int] = mapped_column(default=0)
    questions_correct: Mapped[int] = mapped_column(default=0)  # scored ≥ 60% of the marks
    last_accuracy: Mapped[float | None]  # share of marks earned on this topic in the latest graded attempt
    last_quiz_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
