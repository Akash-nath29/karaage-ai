import uuid

from fastapi import APIRouter

from app.core.permissions import Admin, Viewer
from app.database.session import DbSession
from app.modules.syllabus import service
from app.modules.syllabus.models import Syllabus
from app.modules.syllabus.schemas import (
    LinkSyllabus,
    Structure,
    StructureOut,
    SyllabusDraft,
    SyllabusOut,
    TopicDetail,
    TopicListItem,
)

router = APIRouter(tags=["syllabus"])


@router.get("/courses/{course_id}/syllabus", response_model=SyllabusOut | None)
def get_syllabus(course_id: uuid.UUID, _: Viewer, db: DbSession) -> SyllabusOut | None:
    syllabus = service.get(db, course_id)
    return service.out(syllabus) if syllabus else None


@router.post("/courses/{course_id}/syllabus", response_model=SyllabusOut, status_code=202)
def link_syllabus(course_id: uuid.UUID, data: LinkSyllabus, _: Admin, db: DbSession) -> Syllabus:
    """Use an uploaded document as this course's syllabus and start parsing it."""
    return service.link(db, course_id, data.document_id)


@router.post("/courses/{course_id}/syllabus/parse", response_model=SyllabusOut, status_code=202)
def parse_syllabus(course_id: uuid.UUID, _: Admin, db: DbSession) -> Syllabus:
    return service.reparse(db, course_id)


@router.put("/courses/{course_id}/syllabus/draft", response_model=SyllabusOut)
def save_draft(course_id: uuid.UUID, draft: SyllabusDraft, _: Admin, db: DbSession) -> Syllabus:
    return service.save_draft(db, course_id, draft)


@router.post("/courses/{course_id}/syllabus/confirm", response_model=StructureOut)
def confirm_syllabus(course_id: uuid.UUID, access: Admin, db: DbSession) -> StructureOut:
    return service.confirm(db, course_id, access.user.id)


@router.get("/courses/{course_id}/units", response_model=StructureOut)
def get_structure(course_id: uuid.UUID, access: Viewer, db: DbSession) -> StructureOut:
    return service.structure(db, course_id, access.user.id)


@router.put("/courses/{course_id}/structure", response_model=StructureOut)
def update_structure(course_id: uuid.UUID, tree: Structure, access: Admin, db: DbSession) -> StructureOut:
    return service.update_structure(db, course_id, tree, access.user.id)


@router.get("/courses/{course_id}/topics", response_model=list[TopicListItem])
def list_topics(course_id: uuid.UUID, access: Viewer, db: DbSession) -> list[TopicListItem]:
    return service.topic_list(db, course_id, access.user.id)


@router.get("/topics/{topic_id}", response_model=TopicDetail)
def get_topic(topic_id: uuid.UUID, access: Viewer, db: DbSession) -> TopicDetail:
    return service.topic_detail(db, topic_id, access.user.id)
