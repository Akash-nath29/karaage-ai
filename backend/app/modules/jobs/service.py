import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.ai.providers.base import ProviderError, TransientProviderError
from app.core.exceptions import AppError, NotFoundError
from app.modules.jobs import repository
from app.modules.jobs.models import Job

log = logging.getLogger(__name__)
TERMINAL = {"succeeded", "failed"}
POLL_SECONDS = 1.0
# A job that hasn't reported progress for this long is treated as dead (worker killed, message lost), so the
# user can start it again instead of being told "already running" forever. Every stage emits events.
STALE_AFTER = timedelta(minutes=15)


def get(db: Session, job_id: uuid.UUID) -> Job:
    job = repository.get(db, job_id)
    if job is None:
        raise NotFoundError("Job")
    return job


def is_active(db: Session, job_id: uuid.UUID | None) -> bool:
    """Running or queued, and still reporting progress (see STALE_AFTER)."""
    job = repository.get(db, job_id) if job_id else None
    if job is None or job.status in TERMINAL:
        return False
    last = repository.last_event_at(db, job.id) or job.created_at
    return datetime.now(UTC) - last < STALE_AFTER


def create(db: Session, *, workspace_id: uuid.UUID, kind: str, document_id: uuid.UUID | None = None) -> Job:
    """Started on behalf of whoever the session acts for (the request's user, or the job that queued this one)."""
    job = repository.add(db, Job(workspace_id=workspace_id, kind=kind, document_id=document_id, user_id=db.info.get("user_id")))
    event(db, job, "queued", "Waiting for a worker", 0)
    return job


def event(db: Session, job: Job, stage: str, message: str = "", progress: int | None = None) -> None:
    repository.add_event(db, job.id, stage, message, progress)


def start(db: Session, job: Job, message: str) -> None:
    if job.user_id:
        db.info["user_id"] = job.user_id  # the worker's AI usage is attributed to whoever started the job (D30)
    job.status, job.error = "running", None
    job.attempts += 1
    event(db, job, "started", message, 0)


def succeed(db: Session, job: Job, message: str) -> None:
    job.status, job.finished_at = "succeeded", datetime.now(UTC)
    event(db, job, "succeeded", message, 100)


def fail(db: Session, job: Job, message: str) -> None:
    job.status, job.error, job.finished_at = "failed", message, datetime.now(UTC)
    event(db, job, "failed", message)


def guarded(
    db: Session, job: Job, work: Callable[[], None], on_fail: Callable[[str], None], *, can_retry: bool
) -> bool:
    """Run a background job's work. Returns True when the caller should retry later (transient AI failure).
    Any other failure ends the job via `on_fail(message)` with a message fit for the user."""
    try:
        work()
    except TransientProviderError as e:
        db.rollback()
        if can_retry:
            event(db, job, "retrying", f"AI service unavailable, retrying shortly ({e})")
            db.commit()
            return True
        on_fail(f"The AI service is unavailable: {e}")
    except (AppError, ProviderError) as e:
        db.rollback()
        on_fail(str(e))
    except Exception as e:
        log.exception("job %s failed", job.id)
        db.rollback()
        on_fail(f"Unexpected error: {type(e).__name__}: {e}"[:500])
    return False


def _poll(session_factory: Callable[[], Session], job_id: uuid.UUID, after: int) -> tuple[list[tuple[int, str]], str | None]:
    db = session_factory()
    try:
        # Status first, then events: if the job is terminal now, its final event is already committed.
        job = repository.get(db, job_id)
        status = job.status if job else None
        events = [
            (e.id, json.dumps({"stage": e.stage, "message": e.message, "progress": e.progress}))
            for e in repository.events_after(db, job_id, after)
        ]
        return events, status
    finally:
        db.close()


async def event_stream(session_factory: Callable[[], Session], job_id: uuid.UUID, after: int) -> AsyncIterator[str]:
    """SSE: replay events after `after` (Last-Event-ID), tail new ones, end when the job finishes."""
    # ponytail: polls the DB once a second per open stream; switch to Redis pub/sub if that load shows up.
    while True:
        events, status = await asyncio.to_thread(_poll, session_factory, job_id, after)
        for event_id, data in events:
            after = event_id
            yield f"id: {event_id}\ndata: {data}\n\n"
        if status is None or status in TERMINAL:
            yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
            return
        await asyncio.sleep(POLL_SECONDS)
