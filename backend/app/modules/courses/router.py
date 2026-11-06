import uuid
from collections.abc import Sequence

from fastapi import APIRouter

from app.core.permissions import Admin, Viewer
from app.database.session import DbSession
from app.modules.courses import service
from app.modules.courses.models import Course
from app.modules.courses.schemas import CourseCreate, CourseOut, CourseUpdate

router = APIRouter(tags=["courses"])


@router.post("/workspaces/{workspace_id}/courses", response_model=CourseOut, status_code=201)
def create_course(workspace_id: uuid.UUID, data: CourseCreate, access: Admin, db: DbSession) -> Course:
    return service.create(db, workspace_id, data, access.user.id)


@router.get("/workspaces/{workspace_id}/courses", response_model=list[CourseOut])
def list_courses(workspace_id: uuid.UUID, _: Viewer, db: DbSession) -> Sequence[Course]:
    return service.list_for_workspace(db, workspace_id)


@router.get("/courses/{course_id}", response_model=CourseOut)
def get_course(course_id: uuid.UUID, _: Viewer, db: DbSession) -> Course:
    return service.get(db, course_id)


@router.patch("/courses/{course_id}", response_model=CourseOut)
def update_course(course_id: uuid.UUID, data: CourseUpdate, _: Admin, db: DbSession) -> Course:
    return service.update(db, course_id, data)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: uuid.UUID, access: Admin, db: DbSession) -> None:
    service.delete(db, course_id, access.user.id)
