import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.jobs.models import Job, JobEvent


def get(db: Session, job_id: uuid.UUID) -> Job | None:
    return db.get(Job, job_id)


def add(db: Session, job: Job) -> Job:
    db.add(job)
    db.flush()
    return job


def add_event(db: Session, job_id: uuid.UUID, stage: str, message: str, progress: int | None) -> None:
    db.add(JobEvent(job_id=job_id, stage=stage, message=message, progress=progress))


def last_event_at(db: Session, job_id: uuid.UUID) -> datetime | None:
    return db.scalar(select(func.max(JobEvent.created_at)).where(JobEvent.job_id == job_id))


def events_after(db: Session, job_id: uuid.UUID, after_id: int) -> Sequence[JobEvent]:
    query = select(JobEvent).where(JobEvent.job_id == job_id, JobEvent.id > after_id).order_by(JobEvent.id)
    return db.scalars(query).all()
