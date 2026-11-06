import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AppError, NotFoundError
from app.modules.courses import service as courses
from app.modules.documents import service as documents
from app.modules.jobs import service as jobs
from app.modules.lessons import service as lessons
from app.modules.lessons.models import Lesson, visible_to
from app.modules.rag import repository as chunks
from app.modules.rag.schemas import Passage
from app.modules.syllabus import mapping, repository
from app.modules.syllabus.models import Syllabus, Topic, Unit
from app.modules.syllabus.schemas import (
    Structure,
    StructureOut,
    SubtopicOut,
    SyllabusDraft,
    SyllabusOut,
    TopicDetail,
    TopicListItem,
    TopicOut,
    UnitOut,
)

log = logging.getLogger(__name__)
MATERIALS_SHOWN = 8


def enqueue_parse(job_id: uuid.UUID) -> None:
    # Module-level so tests can run the parse inline instead of going through Redis.
    from app.workers.ingestion_tasks import parse_syllabus

    parse_syllabus.delay(str(job_id))


# --- Syllabus lifecycle: link a document → parse (job) → draft → edit → confirm ------------------------------


def get(db: Session, course_id: uuid.UUID) -> Syllabus | None:
    courses.get(db, course_id)
    return repository.get_for_course(db, course_id)


def out(syllabus: Syllabus) -> SyllabusOut:
    """With the batch-generation estimate a draft's confirm will trigger (Q3)."""
    result = SyllabusOut.model_validate(syllabus)
    if syllabus.status == "draft" and syllabus.draft:
        topics = sum(len(u.get("topics", [])) for u in syllabus.draft.get("units", []))
        result.generation_estimate = lessons.estimate(topics)
    return result


def _require(db: Session, course_id: uuid.UUID) -> Syllabus:
    syllabus = get(db, course_id)
    if syllabus is None:
        raise NotFoundError("Syllabus")
    return syllabus


def _start_parse(db: Session, syllabus: Syllabus, workspace_id: uuid.UUID) -> Syllabus:
    if syllabus.status == "parsing" and jobs.is_active(db, syllabus.job_id):
        raise AppError(409, "The syllabus is already being parsed.")
    job = jobs.create(db, workspace_id=workspace_id, kind="parse_syllabus", document_id=syllabus.document_id)
    syllabus.job_id, syllabus.status, syllabus.error = job.id, "parsing", None
    db.commit()
    try:
        enqueue_parse(job.id)
    except Exception:
        log.exception("could not enqueue syllabus parse job %s", job.id)
        message = "Could not start parsing: the job queue is unavailable. Try again in a moment."
        jobs.fail(db, job, message)
        syllabus.status, syllabus.error = "failed", message
        db.commit()
    return syllabus


def link(db: Session, course_id: uuid.UUID, document_id: uuid.UUID) -> Syllabus:
    course = courses.get(db, course_id)
    document = documents.get(db, document_id)
    if document.workspace_id != course.workspace_id:
        raise AppError(422, "That document belongs to a different workspace.")
    syllabus = repository.get_for_course(db, course_id)
    if syllabus is None:
        syllabus = Syllabus(course_id=course_id)
        db.add(syllabus)
    elif syllabus.status == "parsing" and jobs.is_active(db, syllabus.job_id):
        raise AppError(409, "The syllabus is already being parsed.")
    syllabus.document_id = document.id
    return _start_parse(db, syllabus, course.workspace_id)


def reparse(db: Session, course_id: uuid.UUID) -> Syllabus:
    syllabus = _require(db, course_id)
    if syllabus.document_id is None:
        raise AppError(422, "The syllabus document was deleted. Choose another document.")
    return _start_parse(db, syllabus, courses.get(db, course_id).workspace_id)


def save_draft(db: Session, course_id: uuid.UUID, draft: SyllabusDraft) -> Syllabus:
    syllabus = _require(db, course_id)
    if syllabus.status != "draft":
        raise AppError(409, "There's no draft to edit. Parse the syllabus first.")
    syllabus.draft = draft.model_dump(mode="json")
    db.commit()
    return syllabus


def confirm(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> StructureOut:
    syllabus = _require(db, course_id)
    if syllabus.status != "draft" or not syllabus.draft:
        raise AppError(409, "There's no draft to confirm.")
    apply_structure(db, course_id, SyllabusDraft.model_validate(syllabus.draft))
    syllabus.confirmed, syllabus.status, syllabus.confirmed_at = syllabus.draft, "confirmed", datetime.now(UTC)
    mapping.remap_quietly(db, course_id)
    db.commit()
    lessons.queue_missing(db, course_id, user_id)  # Q3: confirming starts batch generation (cancellable)
    return structure(db, course_id, user_id)


# --- Course structure (C4: rename, add, delete, reorder) ------------------------------------------------------


def _norm(title: str) -> str:
    return " ".join(title.lower().split())


def apply_structure(db: Session, course_id: uuid.UUID, tree: Structure) -> None:
    """Make the course's units/topics match `tree`. Rows are reused by id (editor) or by title (fresh drafts),
    so lessons and progress attached to a topic survive renames, reorders and re-confirmed syllabi."""
    units = {u.id: u for u in repository.units(db, course_id)}
    topics = {t.id: t for t in repository.topics(db, course_id)}
    unit_titles: dict[str, Unit] = {}
    for u in units.values():
        unit_titles.setdefault(_norm(u.title), u)
    topic_titles: dict[tuple[bool, str], Topic] = {}
    for t in topics.values():
        topic_titles.setdefault((t.parent_id is not None, _norm(t.title)), t)
    kept: set[uuid.UUID] = set()

    def reuse(node_id: uuid.UUID | None, by_id: dict, by_title: dict, title_key: object):  # type: ignore[no-untyped-def,type-arg]
        # An unknown id (stale, or another course's) never falls back to a title match: it becomes a new row.
        row = by_id.get(node_id) if node_id else by_title.get(title_key)
        return row if row is not None and row.id not in kept else None

    # Three passes with a flush between each: the models have no ORM relationships, so the flush can't order a
    # new unit before its topics, or a new topic before an existing subtopic being moved under it.
    placed_units = []
    for u_ord, u_node in enumerate(tree.units):
        unit = reuse(u_node.id, units, unit_titles, _norm(u_node.title))
        if unit is None:
            unit = Unit(id=uuid.uuid4(), course_id=course_id)
            db.add(unit)
        unit.title, unit.hours, unit.ordinal = u_node.title, u_node.hours, u_ord
        kept.add(unit.id)
        placed_units.append((unit, u_node))
    db.flush()

    placed_topics = []
    for unit, u_node in placed_units:
        for t_ord, t_node in enumerate(u_node.topics):
            topic = reuse(t_node.id, topics, topic_titles, (False, _norm(t_node.title)))
            if topic is None:
                topic = Topic(id=uuid.uuid4(), course_id=course_id)
                db.add(topic)
            topic.unit_id, topic.parent_id, topic.title, topic.ordinal = unit.id, None, t_node.title, t_ord
            kept.add(topic.id)
            placed_topics.append((topic, t_node))
    db.flush()

    for topic, t_node in placed_topics:
        for s_ord, s_node in enumerate(t_node.subtopics):
            sub = reuse(s_node.id, topics, topic_titles, (True, _norm(s_node.title)))
            if sub is None:
                sub = Topic(id=uuid.uuid4(), course_id=course_id)
                db.add(sub)
            sub.unit_id, sub.parent_id, sub.title, sub.ordinal = topic.unit_id, topic.id, s_node.title, s_ord
            kept.add(sub.id)
    db.flush()  # every kept row is re-parented before the rest is deleted (deletes cascade to children)
    gone_topics = [tid for tid in topics if tid not in kept]
    gone_units = [uid for uid in units if uid not in kept]
    if gone_topics:
        db.execute(delete(Topic).where(Topic.id.in_(gone_topics)))
    if gone_units:
        db.execute(delete(Unit).where(Unit.id.in_(gone_units)))


def update_structure(db: Session, course_id: uuid.UUID, tree: Structure, user_id: uuid.UUID) -> StructureOut:
    courses.get(db, course_id)
    apply_structure(db, course_id, tree)
    mapping.remap_quietly(db, course_id)
    db.commit()
    return structure(db, course_id, user_id)


def _lesson_info(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> dict[uuid.UUID, tuple[uuid.UUID | None, str | None]]:
    """Per topic: the lesson to open (shared first, then the default depth, else any readable one) and its status.
    Only lessons this user can see: shared ones and their own private ones (D28)."""
    info: dict[uuid.UUID, tuple[uuid.UUID | None, str | None]] = {}
    rows = db.scalars(select(Lesson).where(Lesson.course_id == course_id, visible_to(user_id)))
    for lesson in sorted(rows, key=lambda l: (l.visibility != "workspace", l.depth != settings.lesson_default_depth,
                                              not l.current_version)):
        info.setdefault(lesson.topic_id, (lesson.id if lesson.current_version else None, lesson.status))
        if lesson.current_version and info[lesson.topic_id][0] is None:
            info[lesson.topic_id] = (lesson.id, lesson.status)
    return info


def _status(material_count: int, lesson: tuple[uuid.UUID | None, str | None] | None = None) -> str:
    """Topic content status (A1). Per-user states (studied, revision, completed) come with progress (Phase 5)."""
    if lesson and lesson[0]:
        return "lesson_available"
    if lesson and lesson[1] in ("queued", "generating"):
        return "generation_pending"
    return "materials_available" if material_count else "not_started"


def structure(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> StructureOut:
    courses.get(db, course_id)
    counts = repository.material_counts(db, course_id)
    lesson_info = _lesson_info(db, course_id, user_id)
    all_topics = repository.topics(db, course_id)
    children: dict[uuid.UUID, list[Topic]] = {}
    by_unit: dict[uuid.UUID, list[Topic]] = {}
    for t in all_topics:
        (children.setdefault(t.parent_id, []) if t.parent_id else by_unit.setdefault(t.unit_id, [])).append(t)

    def coverage(topic_list: Sequence[Topic]) -> float:
        return round(sum(1 for t in topic_list if counts.get(t.id)) / len(topic_list), 3) if topic_list else 0.0

    units_out = [
        UnitOut(
            id=u.id,
            title=u.title,
            hours=u.hours,
            coverage=coverage(by_unit.get(u.id, [])),
            topics=[
                TopicOut(
                    id=t.id,
                    title=t.title,
                    status=_status(counts.get(t.id, 0), lesson_info.get(t.id)),
                    material_count=counts.get(t.id, 0),
                    lesson_id=lesson_info.get(t.id, (None, None))[0],
                    lesson_status=lesson_info.get(t.id, (None, None))[1],
                    subtopics=[SubtopicOut(id=s.id, title=s.title) for s in children.get(t.id, [])],
                )
                for t in by_unit.get(u.id, [])
            ],
        )
        for u in repository.units(db, course_id)
    ]
    top = [t for t in all_topics if t.parent_id is None]
    ready = sum(1 for t in top if lesson_info.get(t.id, (None, None))[0])
    pending = sum(1 for t in top if lesson_info.get(t.id, (None, None))[1] in ("queued", "generating"))
    return StructureOut(units=units_out, topic_count=len(top), coverage=coverage(top), lessons_ready=ready, lessons_pending=pending)


def topic_list(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> list[TopicListItem]:
    courses.get(db, course_id)
    counts = repository.material_counts(db, course_id)
    lesson_info = _lesson_info(db, course_id, user_id)
    return [
        TopicListItem(
            id=t.id,
            title=t.title,
            unit_id=t.unit_id,
            parent_id=t.parent_id,
            ordinal=t.ordinal,
            status=_status(counts.get(t.id, 0), lesson_info.get(t.id)),
            material_count=counts.get(t.id, 0),
        )
        for t in repository.topics(db, course_id)
    ]


def get_topic(db: Session, topic_id: uuid.UUID) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise NotFoundError("Topic")
    return topic


def topic_detail(db: Session, topic_id: uuid.UUID, user_id: uuid.UUID) -> TopicDetail:
    topic = get_topic(db, topic_id)
    course = courses.get(db, topic.course_id)
    unit = db.get(Unit, topic.unit_id)
    assert unit is not None  # FK
    count = repository.material_counts(db, course.id).get(topic.id, 0)
    lesson = _lesson_info(db, course.id, user_id).get(topic.id)
    subtopics = [t for t in repository.topics(db, course.id) if t.parent_id == topic.id]
    rows = chunks.fetch(db, repository.material_chunk_ids(db, topic.id, MATERIALS_SHOWN))
    return TopicDetail(
        id=topic.id,
        title=topic.title,
        parent_id=topic.parent_id,
        course_id=course.id,
        course_title=course.title,
        workspace_id=course.workspace_id,
        unit_id=unit.id,
        unit_title=unit.title,
        status=_status(count, lesson),
        material_count=count,
        subtopics=[SubtopicOut(id=s.id, title=s.title) for s in subtopics],
        materials=[Passage(chunk_id=r.id, score=0.0, **r._asdict()) for r in rows],
    )
