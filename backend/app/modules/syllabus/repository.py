import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.rag.models import DocumentChunk
from app.modules.syllabus.models import Syllabus, Topic, Unit


def get_for_course(db: Session, course_id: uuid.UUID) -> Syllabus | None:
    return db.scalar(select(Syllabus).where(Syllabus.course_id == course_id))


def get_by_job(db: Session, job_id: uuid.UUID) -> Syllabus | None:
    return db.scalar(select(Syllabus).where(Syllabus.job_id == job_id))


def units(db: Session, course_id: uuid.UUID) -> Sequence[Unit]:
    return db.scalars(select(Unit).where(Unit.course_id == course_id).order_by(Unit.ordinal)).all()


def topics(db: Session, course_id: uuid.UUID) -> Sequence[Topic]:
    return db.scalars(select(Topic).where(Topic.course_id == course_id).order_by(Topic.ordinal)).all()


def material_counts(db: Session, course_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(DocumentChunk.topic_id, func.count())
        .join(Topic, Topic.id == DocumentChunk.topic_id)
        .where(Topic.course_id == course_id)
        .group_by(DocumentChunk.topic_id)
    )
    return {topic_id: count for topic_id, count in rows}


def material_chunk_ids(db: Session, topic_id: uuid.UUID, limit: int) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(DocumentChunk.id)
            .where(DocumentChunk.topic_id == topic_id)
            .order_by(DocumentChunk.document_id, DocumentChunk.ordinal)
            .limit(limit)
        )
    )
