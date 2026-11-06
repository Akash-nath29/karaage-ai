import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class ResearchJob(Base):
    """One research run for a topic (PRD E2): what the student's materials cover, the searches made, and claims
    cross-checked across sources. Progress streams through the generic job (`job_id`)."""

    __tablename__ = "research_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID | None]
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | succeeded | failed
    error: Mapped[str | None] = mapped_column(Text)
    sufficient: Mapped[bool | None]  # could the student's materials alone teach the topic? (A20)
    covered: Mapped[list[str]] = mapped_column(JSONB, default=list)
    missing: Mapped[list[str]] = mapped_column(JSONB, default=list)
    queries: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # [{"claim", "status": verified|unverified|disputed, "sources": [source ids], "materials": [chunk ids],
    #   "contradicting": [source ids]}]: web and uploaded-material citations kept apart (PRD E5)
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    source_count: Mapped[int] = mapped_column(default=0)
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    # clock_timestamp(), not now(): "latest run" orders by this, and now() is the transaction's start time
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())
    finished_at: Mapped[datetime | None]


class ResearchSource(Base):
    """A web source kept for a research run, with the passages relevant to the topic (PRD E5)."""

    __tablename__ = "research_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_jobs.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(30))  # academic | official_docs | encyclopedia | educational | …
    quality: Mapped[float]
    relevance: Mapped[float]
    published_date: Mapped[str | None] = mapped_column(String(50))
    retrieved_at: Mapped[datetime] = mapped_column(server_default=func.now())
    content_kind: Mapped[str] = mapped_column(String(10))  # page (full text) | snippet (search excerpt only)
    passages: Mapped[list[str]] = mapped_column(JSONB, default=list)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")  # verified | unverified | disputed
