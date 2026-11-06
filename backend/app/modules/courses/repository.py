import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.courses.models import Course


def list_for_workspace(db: Session, workspace_id: uuid.UUID) -> Sequence[Course]:
    query = select(Course).where(Course.workspace_id == workspace_id).order_by(Course.created_at.desc())
    return db.scalars(query).all()


def get(db: Session, course_id: uuid.UUID) -> Course | None:
    return db.get(Course, course_id)


def add(db: Session, course: Course) -> Course:
    db.add(course)
    db.flush()
    return course


def delete(db: Session, course: Course) -> None:
    db.delete(course)
