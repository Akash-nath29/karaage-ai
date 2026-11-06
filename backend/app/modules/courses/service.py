import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.courses import repository
from app.modules.courses.models import Course
from app.modules.courses.schemas import CourseCreate, CourseUpdate
from app.modules.users.service import audit
from app.modules.workspaces import service as workspaces


def list_for_workspace(db: Session, workspace_id: uuid.UUID) -> Sequence[Course]:
    workspaces.get(db, workspace_id)  # 404 for unknown workspace instead of an empty list
    return repository.list_for_workspace(db, workspace_id)


def get(db: Session, course_id: uuid.UUID) -> Course:
    course = repository.get(db, course_id)
    if course is None:
        raise NotFoundError("Course")
    return course


def create(db: Session, workspace_id: uuid.UUID, data: CourseCreate, user_id: uuid.UUID) -> Course:
    workspaces.get(db, workspace_id)
    course = repository.add(db, Course(workspace_id=workspace_id, created_by=user_id, **data.model_dump()))
    db.commit()
    return course


def update(db: Session, course_id: uuid.UUID, data: CourseUpdate) -> Course:
    course = get(db, course_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(course, field, value)
    db.commit()
    return course


def delete(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> None:
    course = get(db, course_id)
    audit(db, "course.deleted", user_id=user_id, workspace_id=course.workspace_id, target=course.title)
    repository.delete(db, course)
    db.commit()
