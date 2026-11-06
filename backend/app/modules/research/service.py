import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import NotFoundError
from app.modules.courses import service as courses
from app.modules.jobs import service as jobs
from app.modules.research.models import ResearchJob, ResearchSource
from app.modules.syllabus import service as syllabus

log = logging.getLogger(__name__)


def enqueue_research(research_id: uuid.UUID) -> None:
    # Module-level so tests can run research inline instead of going through Redis.
    from app.workers.research_tasks import run_research

    run_research.delay(str(research_id))


def latest_for_topic(db: Session, topic_id: uuid.UUID) -> ResearchJob | None:
    syllabus.get_topic(db, topic_id)
    return db.scalar(
        select(ResearchJob).where(ResearchJob.topic_id == topic_id).order_by(ResearchJob.created_at.desc()).limit(1)
    )


def request(db: Session, topic_id: uuid.UUID, *, refresh: bool) -> ResearchJob:
    """Start research for a topic, or return a running/recent one (PRD §12.2: reuse research when appropriate)."""
    topic = syllabus.get_topic(db, topic_id)
    latest = latest_for_topic(db, topic_id)
    if latest and latest.status in ("queued", "running") and jobs.is_active(db, latest.job_id):
        return latest
    fresh_after = datetime.now(UTC) - timedelta(days=settings.research_reuse_days)
    if latest and not refresh and latest.status == "succeeded" and latest.created_at >= fresh_after:
        return latest

    research = create(db, topic.id)
    try:
        enqueue_research(research.id)
    except Exception:
        log.exception("could not enqueue research %s", research.id)
        message = "Could not start research: the job queue is unavailable. Try again in a moment."
        assert research.job_id is not None
        jobs.fail(db, jobs.get(db, research.job_id), message)
        research.status, research.error, research.finished_at = "failed", message, datetime.now(UTC)
        db.commit()
    return research


def create(db: Session, topic_id: uuid.UUID) -> ResearchJob:
    """A queued research run and its progress job, committed, not dispatched (lesson generation runs it inline)."""
    workspace_id = courses.get(db, syllabus.get_topic(db, topic_id).course_id).workspace_id
    job = jobs.create(db, workspace_id=workspace_id, kind="research")
    research = ResearchJob(topic_id=topic_id, workspace_id=workspace_id, job_id=job.id)
    db.add(research)
    db.commit()
    return research


def fresh_for_topic(db: Session, topic_id: uuid.UUID) -> ResearchJob | None:
    """The latest succeeded run, if recent enough to reuse (PRD §12.2)."""
    latest = latest_for_topic(db, topic_id)
    fresh_after = datetime.now(UTC) - timedelta(days=settings.research_reuse_days)
    if latest and latest.status == "succeeded" and latest.created_at >= fresh_after:
        return latest
    return None


def get(db: Session, research_id: uuid.UUID) -> ResearchJob:
    research = db.get(ResearchJob, research_id)
    if research is None:
        raise NotFoundError("Research")
    return research


def refresh(db: Session, research_id: uuid.UUID) -> ResearchJob:
    return request(db, get(db, research_id).topic_id, refresh=True)


def sources(db: Session, research_id: uuid.UUID) -> Sequence[ResearchSource]:
    get(db, research_id)
    return db.scalars(
        select(ResearchSource)
        .where(ResearchSource.research_id == research_id)
        .order_by(ResearchSource.quality.desc(), ResearchSource.relevance.desc())
    ).all()
