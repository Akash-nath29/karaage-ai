import uuid
from collections.abc import Sequence

from fastapi import APIRouter

from app.core.permissions import Editor, Viewer
from app.database.session import DbSession
from app.modules.documents.models import Document
from app.modules.lessons import service
from app.modules.lessons.models import Lesson, LessonVersion
from app.modules.lessons.schemas import (
    BatchResult,
    EnrichRequest,
    FeedbackIn,
    GenerateRequest,
    LessonDetail,
    LessonListItem,
    LessonOut,
    PinIn,
    PinnedDocument,
    VersionMeta,
)

router = APIRouter(tags=["lessons"])


@router.post("/topics/{topic_id}/lessons/generate", response_model=LessonOut, status_code=202)
def generate_lesson(topic_id: uuid.UUID, access: Viewer, db: DbSession, data: GenerateRequest | None = None) -> Lesson:
    """Generate a topic's lesson at a depth (first version, or a new version if it exists). Shared for editors and
    above unless they ask for private; always private for viewers (D28)."""
    data = data or GenerateRequest()
    return service.generate(db, access, topic_id, data.depth, data.visibility)


@router.get("/topics/{topic_id}/lessons", response_model=list[LessonOut])
def topic_lessons(topic_id: uuid.UUID, access: Viewer, db: DbSession) -> Sequence[Lesson]:
    """Shared lessons and your private ones."""
    return service.for_topic(db, topic_id, access.user.id)


@router.get("/workspaces/{workspace_id}/lessons", response_model=list[LessonListItem])
def workspace_lessons(workspace_id: uuid.UUID, access: Viewer, db: DbSession) -> list[LessonListItem]:
    """Readable lessons across the workspace's courses, newest first (shared learning resources)."""
    return service.for_workspace(db, workspace_id, access.user.id)


@router.get("/lessons/{lesson_id}", response_model=LessonDetail)
def get_lesson(lesson_id: uuid.UUID, _: Viewer, db: DbSession, version: int | None = None) -> LessonDetail:
    return service.detail(db, lesson_id, version)


@router.get("/lessons/{lesson_id}/versions", response_model=list[VersionMeta])
def lesson_versions(lesson_id: uuid.UUID, _: Viewer, db: DbSession) -> Sequence[LessonVersion]:
    return service.versions(db, lesson_id)


@router.post("/lessons/{lesson_id}/regenerate", response_model=LessonOut, status_code=202)
def regenerate_lesson(lesson_id: uuid.UUID, access: Viewer, db: DbSession) -> Lesson:
    """Shared lessons: editors and above. Private lessons: their owner."""
    return service.regenerate(db, access, lesson_id)


@router.post("/lessons/{lesson_id}/enrich", response_model=LessonOut, status_code=202)
def enrich_lesson(lesson_id: uuid.UUID, data: EnrichRequest, access: Viewer, db: DbSession) -> Lesson:
    """Add one section answering a request (PRD F1 mode 2): a new version, without regenerating the lesson."""
    return service.enrich(db, access, lesson_id, data.request)


@router.post("/lessons/{lesson_id}/publish", response_model=LessonOut)
def publish_lesson(lesson_id: uuid.UUID, access: Editor, db: DbSession) -> Lesson:
    """Share your private lesson with the workspace (B4)."""
    return service.publish(db, access, lesson_id)


@router.post("/lessons/{lesson_id}/feedback", status_code=204)
def lesson_feedback(lesson_id: uuid.UUID, data: FeedbackIn, access: Viewer, db: DbSession) -> None:
    service.feedback(db, access.user.id, lesson_id, data.rating, data.comment)


@router.post("/courses/{course_id}/lessons/generate", response_model=BatchResult, status_code=202)
def generate_course_lessons(course_id: uuid.UUID, access: Editor, db: DbSession, data: GenerateRequest | None = None) -> BatchResult:
    """Queue shared lessons for every topic that doesn't have one at this depth."""
    return BatchResult(count=service.queue_missing(db, course_id, access.user.id, data.depth if data else None))


@router.post("/courses/{course_id}/lessons/cancel", response_model=BatchResult)
def cancel_course_lessons(course_id: uuid.UUID, _: Editor, db: DbSession) -> BatchResult:
    return BatchResult(count=service.cancel_queued(db, course_id))


@router.get("/topics/{topic_id}/documents", response_model=list[PinnedDocument])
def pinned_documents(topic_id: uuid.UUID, _: Viewer, db: DbSession) -> Sequence[Document]:
    return service.pins(db, topic_id)


@router.put("/topics/{topic_id}/documents", response_model=list[PinnedDocument])
def pin_documents(topic_id: uuid.UUID, data: PinIn, _: Editor, db: DbSession) -> Sequence[Document]:
    """Documents always offered as evidence for this topic's lessons (manual mapping, D12)."""
    return service.set_pins(db, topic_id, data.document_ids)
