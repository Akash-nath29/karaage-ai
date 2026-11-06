import logging
import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AppError, NotFoundError
from app.core.permissions import Access
from app.modules.courses.models import Course
from app.modules.documents.models import Document
from app.modules.jobs import service as jobs
from app.modules.lessons.document import DEPTHS
from app.modules.lessons.models import Lesson, LessonCitation, LessonFeedback, LessonVersion, visible_to
from app.modules.lessons.schemas import CitationOut, LessonDetail, LessonListItem, LessonOut, VersionMeta
from app.modules.rag.models import DocumentChunk
from app.modules.syllabus.models import DocumentTopic, Topic, Unit
from app.modules.users.service import audit

log = logging.getLogger(__name__)

# Rough per-lesson cost for the estimate shown before a batch (Q3): research plan + verify + lesson + slack.
CALLS_PER_LESSON, TOKENS_PER_LESSON = 4, 30_000


def enqueue_generation(lesson_id: uuid.UUID, request: str | None = None) -> None:
    # Module-level so tests can run generation inline instead of going through Redis.
    from app.workers.generation_tasks import generate_lesson

    generate_lesson.delay(str(lesson_id), request)


def estimate(lessons: int) -> dict[str, int]:
    return {
        "lessons": lessons,
        "ai_calls": lessons * CALLS_PER_LESSON,
        "tokens": lessons * TOKENS_PER_LESSON,
        "web_searches_max": lessons * settings.research_max_queries,  # only where materials fall short (E1)
    }


def _topic(db: Session, topic_id: uuid.UUID) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise NotFoundError("Topic")
    return topic


def get(db: Session, lesson_id: uuid.UUID) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise NotFoundError("Lesson")
    return lesson


def _start(db: Session, lesson: Lesson, request: str | None = None) -> Lesson:
    if jobs.is_active(db, lesson.job_id):
        raise AppError(409, "This lesson is already being generated.")
    job = jobs.create(db, workspace_id=lesson.workspace_id, kind="enrich_lesson" if request else "generate_lesson")
    lesson.job_id, lesson.status, lesson.error = job.id, "queued", None
    db.commit()
    try:
        enqueue_generation(lesson.id, request)
    except Exception:
        log.exception("could not enqueue lesson %s", lesson.id)
        message = "Could not start: the job queue is unavailable. Try again in a moment."
        jobs.fail(db, job, message)
        lesson.status, lesson.error = "failed", message
        db.commit()
    return lesson


def _lesson_for(db: Session, topic: Topic, depth: str | None, visibility: str, user_id: uuid.UUID) -> Lesson:
    """The shared lesson, or this user's private one, for a topic and depth; created if missing (D28)."""
    depth = depth or settings.lesson_default_depth
    if depth not in DEPTHS:
        raise AppError(422, f"Unknown depth {depth!r}.")
    query = select(Lesson).where(Lesson.topic_id == topic.id, Lesson.depth == depth, Lesson.visibility == visibility)
    lesson = db.scalar(query.where(Lesson.owner_id == user_id) if visibility == "private" else query)
    if lesson is None:
        course = db.get(Course, topic.course_id)
        assert course is not None  # FK
        lesson = Lesson(workspace_id=course.workspace_id, course_id=course.id, topic_id=topic.id, depth=depth,
                        visibility=visibility, owner_id=user_id)
        db.add(lesson)
        db.flush()
    return lesson


def generate(db: Session, access: Access, topic_id: uuid.UUID, depth: str | None, visibility: str | None = None) -> Lesson:
    """Generate a topic's lesson at a depth: the first version, or a new version of an existing lesson.
    Editors and above make shared lessons by default; viewers make private ones (PRD §4.2, D28)."""
    visibility = visibility or ("workspace" if access.at_least("editor") else "private")
    if visibility == "workspace" and not access.at_least("editor"):
        raise AppError(403, "Viewers can generate private lessons only.")
    return _start(db, _lesson_for(db, _topic(db, topic_id), depth, visibility, access.user.id))


def queue_missing(db: Session, course_id: uuid.UUID, user_id: uuid.UUID, depth: str | None = None) -> int:
    """Batch generation (PRD F1 mode 1, Q3): every top-level topic without a shared lesson at this depth."""
    depth = depth or settings.lesson_default_depth
    topics = db.scalars(select(Topic).where(Topic.course_id == course_id, Topic.parent_id.is_(None)).order_by(Topic.ordinal))
    existing = {l.topic_id: l for l in db.scalars(select(Lesson).where(
        Lesson.course_id == course_id, Lesson.depth == depth, Lesson.visibility == "workspace"))}
    queued = 0
    for topic in topics:
        lesson = existing.get(topic.id)
        if lesson and (lesson.current_version or jobs.is_active(db, lesson.job_id)):
            continue
        _start(db, _lesson_for(db, topic, depth, "workspace", user_id))
        queued += 1
    return queued


def cancel_queued(db: Session, course_id: uuid.UUID) -> int:
    """Stop a batch: shared lessons not started yet are cancelled (their tasks skip). Running ones finish."""
    lessons = list(db.scalars(select(Lesson).where(
        Lesson.course_id == course_id, Lesson.status == "queued", Lesson.visibility == "workspace")))
    for lesson in lessons:
        lesson.status = "cancelled"
        if lesson.job_id:
            jobs.fail(db, jobs.get(db, lesson.job_id), "Cancelled")
    db.commit()
    return len(lessons)


def _editable(db: Session, access: Access, lesson_id: uuid.UUID) -> Lesson:
    """Shared lessons change only by editors and above (A11); private ones only by their owner (the route's check)."""
    lesson = get(db, lesson_id)
    if lesson.visibility == "workspace" and not access.at_least("editor"):
        raise AppError(403, "Only editors and above can change shared lessons. Generate your own private version instead.")
    return lesson


def regenerate(db: Session, access: Access, lesson_id: uuid.UUID) -> Lesson:
    return _start(db, _editable(db, access, lesson_id))


def enrich(db: Session, access: Access, lesson_id: uuid.UUID, request: str) -> Lesson:
    lesson = _editable(db, access, lesson_id)
    if not lesson.current_version:
        raise AppError(409, "Generate the lesson before asking for more.")
    return _start(db, lesson, request)


def publish(db: Session, access: Access, lesson_id: uuid.UUID) -> Lesson:
    """Share your private lesson with the workspace (PRD §7, B4, D28)."""
    lesson = get(db, lesson_id)
    if lesson.visibility == "workspace":
        raise AppError(409, "This lesson is already shared.")
    if not lesson.current_version:
        raise AppError(409, "Generate the lesson before sharing it.")
    if db.scalar(select(Lesson.id).where(Lesson.topic_id == lesson.topic_id, Lesson.depth == lesson.depth,
                                         Lesson.visibility == "workspace")):
        raise AppError(409, "This topic already has a shared lesson at this depth. Regenerate that one instead.")
    lesson.visibility = "workspace"
    topic = _topic(db, lesson.topic_id)
    audit(db, "lesson.published", user_id=access.user.id, workspace_id=lesson.workspace_id, target=topic.title,
          depth=lesson.depth)
    db.commit()
    return lesson


def for_topic(db: Session, topic_id: uuid.UUID, user_id: uuid.UUID) -> Sequence[Lesson]:
    _topic(db, topic_id)
    return db.scalars(select(Lesson).where(Lesson.topic_id == topic_id, visible_to(user_id))
                      .order_by(Lesson.visibility.desc(), Lesson.created_at)).all()


def for_workspace(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> list[LessonListItem]:
    """Lessons with something to read: shared ones and your private ones (shared learning resources, Phase 6)."""
    rows = db.execute(
        select(Lesson, Course.title, Topic.title, LessonVersion.created_at)
        .join(Course, Course.id == Lesson.course_id).join(Topic, Topic.id == Lesson.topic_id)
        .join(LessonVersion, (LessonVersion.lesson_id == Lesson.id) & (LessonVersion.version == Lesson.current_version))
        .where(Lesson.workspace_id == workspace_id, visible_to(user_id))
        .order_by(LessonVersion.created_at.desc()))
    return [LessonListItem(**LessonOut.model_validate(lesson).model_dump(), course_title=course, topic_title=topic,
                           updated_at=updated) for lesson, course, topic, updated in rows]


def versions(db: Session, lesson_id: uuid.UUID) -> Sequence[LessonVersion]:
    get(db, lesson_id)
    return db.scalars(select(LessonVersion).where(LessonVersion.lesson_id == lesson_id).order_by(LessonVersion.version.desc())).all()


def detail(db: Session, lesson_id: uuid.UUID, version: int | None) -> LessonDetail:
    lesson = get(db, lesson_id)
    number = version or lesson.current_version
    found = db.scalar(select(LessonVersion).where(LessonVersion.lesson_id == lesson.id, LessonVersion.version == number))
    if found is None:
        raise NotFoundError("Lesson version")
    topic = _topic(db, lesson.topic_id)
    unit, course = db.get(Unit, topic.unit_id), db.get(Course, topic.course_id)
    assert unit is not None and course is not None  # FKs
    citations = list(db.scalars(select(LessonCitation).where(LessonCitation.version_id == found.id).order_by(LessonCitation.label)))
    alive = set(db.scalars(select(Document.id).where(Document.id.in_({c.document_id for c in citations if c.document_id}))))
    return LessonDetail(
        lesson=LessonOut.model_validate(lesson), workspace_id=lesson.workspace_id,
        course_id=course.id, course_title=course.title, unit_title=unit.title, topic_title=topic.title,
        version=VersionMeta.model_validate(found),
        document=found.document,
        citations=[CitationOut.model_validate(c).model_copy(update={"available": c.kind == "web" or c.document_id in alive})
                   for c in citations],
    )


def feedback(db: Session, user_id: uuid.UUID, lesson_id: uuid.UUID, rating: int, comment: str) -> None:
    lesson = get(db, lesson_id)
    if not lesson.current_version:
        raise AppError(409, "There's no lesson to rate yet.")
    db.add(LessonFeedback(lesson_id=lesson.id, user_id=user_id, version=lesson.current_version, rating=rating,
                          comment=comment))
    db.commit()


# --- Outdated lessons (PRD F7) -----------------------------------------------------------------------------------


def _current_versions(db: Session):  # type: ignore[no-untyped-def]
    return select(Lesson).join(
        LessonVersion, (LessonVersion.lesson_id == Lesson.id) & (LessonVersion.version == Lesson.current_version)
    )


def flag_document_changed(db: Session, document_id: uuid.UUID, reason: str) -> int:
    """Lessons whose current version cites this document. The caller commits."""
    lessons = list(db.scalars(_current_versions(db).where(LessonVersion.document_ids.contains([document_id]))))
    for lesson in lessons:
        lesson.outdated_reason = reason
    return len(lessons)


def flag_new_material(db: Session, document_id: uuid.UUID) -> int:
    """Lessons on topics that this (newly processed) document now has passages for. The caller commits."""
    topic_ids = set(db.scalars(select(DocumentChunk.topic_id).where(
        DocumentChunk.document_id == document_id, DocumentChunk.topic_id.is_not(None))))
    if not topic_ids:
        return 0
    lessons = list(db.scalars(_current_versions(db).where(
        Lesson.topic_id.in_(topic_ids), ~LessonVersion.document_ids.contains([document_id]))))
    for lesson in lessons:
        lesson.outdated_reason = "New material for this topic was uploaded after this version."
    return len(lessons)


# --- Pinned documents (C4 manual mapping, D12) --------------------------------------------------------------------


def pins(db: Session, topic_id: uuid.UUID) -> Sequence[Document]:
    _topic(db, topic_id)
    return db.scalars(
        select(Document).join(DocumentTopic, DocumentTopic.document_id == Document.id)
        .where(DocumentTopic.topic_id == topic_id).order_by(Document.filename)
    ).all()


def set_pins(db: Session, topic_id: uuid.UUID, document_ids: list[uuid.UUID]) -> Sequence[Document]:
    topic = _topic(db, topic_id)
    course = db.get(Course, topic.course_id)
    assert course is not None  # FK
    found = set(db.scalars(select(Document.id).where(Document.id.in_(document_ids), Document.workspace_id == course.workspace_id)))
    if missing := set(document_ids) - found:
        raise AppError(422, f"{len(missing)} document(s) aren't in this workspace.")
    db.execute(delete(DocumentTopic).where(DocumentTopic.topic_id == topic_id))
    db.add_all(DocumentTopic(document_id=d, topic_id=topic_id) for d in dict.fromkeys(document_ids))
    db.commit()
    return pins(db, topic_id)
