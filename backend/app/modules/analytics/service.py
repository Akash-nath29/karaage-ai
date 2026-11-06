"""Topic progress (PRD H6, A14) and learning analytics (Module I). Per user; all thresholds live here."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.analytics.models import TopicProgress
from app.modules.assessments.models import Quiz, QuizAttempt
from app.modules.courses.models import Course
from app.modules.lessons.models import Lesson, LessonVersion, visible_to
from app.modules.syllabus.models import Topic, Unit
from app.modules.tutor.models import TutorSession
from app.modules.workspaces.models import Workspace, WorkspaceMember

if TYPE_CHECKING:
    from app.modules.assessments.models import Question

COMPLETED_AT, REVISION_BELOW, CORRECT_AT = 0.7, 0.5, 0.6  # A14: completed ≥ 70%, revision < 50%; "correct" ≥ 60%
STALE_AFTER = timedelta(days=14)  # A14: studied this long ago with no quiz since → revision required
STRONG_AT = 0.8
RECENT = 5  # items in the dashboard's recent lists


class TopicProgressOut(BaseModel):
    topic_id: uuid.UUID
    title: str
    unit_id: uuid.UUID
    status: str  # not_started | studied | revision_required | completed
    studied_at: datetime | None
    questions_attempted: int
    questions_correct: int
    accuracy: float | None  # all-time share of questions answered correctly
    last_accuracy: float | None  # share of marks in the latest quiz
    last_quiz_at: datetime | None
    revise_by: datetime | None  # revision schedule (H6)


class UnitProgressOut(BaseModel):
    unit_id: uuid.UUID
    title: str
    topics: int
    completed: int
    studied: int  # marked studied (whatever the latest quiz says)


class CourseProgress(BaseModel):
    course_id: uuid.UUID
    topics: list[TopicProgressOut]
    units: list[UnitProgressOut]
    completed: int
    studied: int
    revision_required: int
    questions_attempted: int
    accuracy: float | None
    weak_topics: list[uuid.UUID]
    strong_topics: list[uuid.UUID]


def status(p: TopicProgress | None, now: datetime) -> str:
    if p is None:
        return "not_started"
    last_activity = max(d for d in (p.studied_at, p.last_quiz_at, datetime.min.replace(tzinfo=UTC)) if d)
    if p.last_accuracy is not None and p.last_accuracy < REVISION_BELOW:
        return "revision_required"
    if p.studied_at and now - last_activity > STALE_AFTER:
        return "revision_required"
    if p.studied_at and p.last_accuracy is not None and p.last_accuracy >= COMPLETED_AT:
        return "completed"
    return "studied" if p.studied_at else "not_started"


def _row(db: Session, user_id: uuid.UUID, topic: Topic) -> TopicProgress:
    row = db.get(TopicProgress, (user_id, topic.id))
    if row is None:
        course = db.get(Course, topic.course_id)
        assert course is not None  # FK
        row = TopicProgress(user_id=user_id, topic_id=topic.id, workspace_id=course.workspace_id, course_id=course.id,
                            questions_attempted=0, questions_correct=0)
        db.add(row)
    return row


def set_studied(db: Session, user_id: uuid.UUID, topic_id: uuid.UUID, studied: bool) -> TopicProgressOut:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise NotFoundError("Topic")
    row = _row(db, user_id, topic)
    row.studied_at = datetime.now(UTC) if studied else None
    row.updated_at = datetime.now(UTC)
    db.commit()
    return _out(topic, row, datetime.now(UTC))


def record_attempt(db: Session, user_id: uuid.UUID, graded: "list[tuple[Question, float, float]]") -> None:
    """Fold a graded attempt into the student's progress per topic: (question, score, max). The caller commits."""
    per_topic: dict[uuid.UUID, list[float]] = {}
    for question, score, maximum in graded:
        if question.topic_id:
            earned, total, attempted, correct = per_topic.setdefault(question.topic_id, [0.0, 0.0, 0, 0])
            per_topic[question.topic_id] = [earned + score, total + maximum, attempted + 1,
                                            correct + (maximum > 0 and score / maximum >= CORRECT_AT)]
    now = datetime.now(UTC)
    for topic_id, (earned, total, attempted, correct) in per_topic.items():
        topic = db.get(Topic, topic_id)
        if topic is None:
            continue
        row = _row(db, user_id, topic)
        row.questions_attempted += int(attempted)
        row.questions_correct += int(correct)
        row.last_accuracy = round(earned / total, 3) if total else None
        row.last_quiz_at = row.updated_at = now


def _out(topic: Topic, row: TopicProgress | None, now: datetime) -> TopicProgressOut:
    state = status(row, now)
    last_activity = max((d for d in (row.studied_at, row.last_quiz_at) if d), default=None) if row else None
    revise_by = now if state == "revision_required" else (last_activity + STALE_AFTER if last_activity else None)
    return TopicProgressOut(
        topic_id=topic.id, title=topic.title, unit_id=topic.unit_id, status=state,
        studied_at=row.studied_at if row else None,
        questions_attempted=row.questions_attempted if row else 0,
        questions_correct=row.questions_correct if row else 0,
        accuracy=round(row.questions_correct / row.questions_attempted, 3) if row and row.questions_attempted else None,
        last_accuracy=row.last_accuracy if row else None, last_quiz_at=row.last_quiz_at if row else None,
        revise_by=revise_by,
    )


def course_progress(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> CourseProgress:
    if db.get(Course, course_id) is None:
        raise NotFoundError("Course")
    now = datetime.now(UTC)
    units = list(db.scalars(select(Unit).where(Unit.course_id == course_id).order_by(Unit.ordinal)))
    order = {u.id: u.ordinal for u in units}
    topics = sorted(db.scalars(select(Topic).where(Topic.course_id == course_id, Topic.parent_id.is_(None))),
                    key=lambda t: (order.get(t.unit_id, 0), t.ordinal))
    rows = {r.topic_id: r for r in db.scalars(select(TopicProgress).where(
        TopicProgress.course_id == course_id, TopicProgress.user_id == user_id))}
    out = [_out(t, rows.get(t.id), now) for t in topics]
    attempted = sum(t.questions_attempted for t in out)
    quizzed = [t for t in out if t.last_accuracy is not None]
    return CourseProgress(
        course_id=course_id, topics=out,
        units=[UnitProgressOut(
            unit_id=u.id, title=u.title, topics=sum(1 for t in out if t.unit_id == u.id),
            completed=sum(1 for t in out if t.unit_id == u.id and t.status == "completed"),
            studied=sum(1 for t in out if t.unit_id == u.id and t.studied_at),
        ) for u in units],
        completed=sum(1 for t in out if t.status == "completed"),
        studied=sum(1 for t in out if t.studied_at),
        revision_required=sum(1 for t in out if t.status == "revision_required"),
        questions_attempted=attempted,
        accuracy=round(sum(t.questions_correct for t in out) / attempted, 3) if attempted else None,
        weak_topics=[t.topic_id for t in sorted(quizzed, key=lambda t: t.last_accuracy or 0) if (t.last_accuracy or 0) < REVISION_BELOW],
        strong_topics=[t.topic_id for t in quizzed if (t.last_accuracy or 0) >= STRONG_AT],
    )


# --- Learning analytics (Module I, D31) ---------------------------------------------------------------------------


class CourseSummary(BaseModel):
    course_id: uuid.UUID
    title: str
    workspace_id: uuid.UUID
    workspace_name: str
    topics: int
    completed: int
    studied: int
    revision_required: int
    accuracy: float | None


class TopicRef(BaseModel):
    topic_id: uuid.UUID
    title: str
    course_id: uuid.UUID
    course_title: str
    last_accuracy: float | None
    revise_by: datetime | None


class RecentLesson(BaseModel):
    lesson_id: uuid.UUID
    topic_title: str
    course_title: str
    depth: str
    visibility: str
    updated_at: datetime


class RecentSession(BaseModel):
    session_id: uuid.UUID
    title: str
    course_title: str | None
    updated_at: datetime


class LearningAnalytics(BaseModel):
    courses_enrolled: int
    topics_completed: int
    topics_remaining: int
    lessons_generated: int
    quiz_attempts: int
    average_accuracy: float | None  # marks earned / marks available over your graded attempts
    weak_topics: list[TopicRef]
    revision_due: list[TopicRef]
    courses: list[CourseSummary]
    recent_lessons: list[RecentLesson]
    recent_sessions: list[RecentSession]  # "continue learning"


def learning_analytics(db: Session, user_id: uuid.UUID) -> LearningAnalytics:
    mine = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
    courses: list[CourseSummary] = []
    weak: list[TopicRef] = []
    due: list[TopicRef] = []
    for course, workspace_name in db.execute(select(Course, Workspace.name).join(Workspace, Workspace.id == Course.workspace_id)
                                             .where(Course.workspace_id.in_(mine)).order_by(Course.created_at.desc())):
        p = course_progress(db, course.id, user_id)
        courses.append(CourseSummary(course_id=course.id, title=course.title, workspace_id=course.workspace_id,
                                     workspace_name=workspace_name, topics=len(p.topics), completed=p.completed,
                                     studied=p.studied, revision_required=p.revision_required, accuracy=p.accuracy))
        by_id = {t.topic_id: t for t in p.topics}

        def ref(t: TopicProgressOut) -> TopicRef:
            return TopicRef(topic_id=t.topic_id, title=t.title, course_id=course.id, course_title=course.title,  # noqa: B023
                            last_accuracy=t.last_accuracy, revise_by=t.revise_by)

        weak += [ref(by_id[t]) for t in p.weak_topics]
        due += [ref(t) for t in p.topics if t.status == "revision_required"]

    earned, possible, attempts = db.execute(
        select(func.coalesce(func.sum(QuizAttempt.score), 0), func.coalesce(func.sum(QuizAttempt.max_score), 0), func.count())
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(Quiz.user_id == user_id, Quiz.workspace_id.in_(mine), QuizAttempt.status == "graded")).one()
    readable = (Lesson.workspace_id.in_(mine), visible_to(user_id), Lesson.current_version > 0)
    recent = db.execute(
        select(Lesson, Topic.title, Course.title, LessonVersion.created_at)
        .join(Topic, Topic.id == Lesson.topic_id).join(Course, Course.id == Lesson.course_id)
        .join(LessonVersion, (LessonVersion.lesson_id == Lesson.id) & (LessonVersion.version == Lesson.current_version))
        .where(*readable).order_by(LessonVersion.created_at.desc()).limit(RECENT))
    sessions = db.execute(
        select(TutorSession, Course.title).outerjoin(Course, Course.id == TutorSession.course_id)
        .where(TutorSession.user_id == user_id, TutorSession.workspace_id.in_(mine))
        .order_by(TutorSession.updated_at.desc()).limit(RECENT))
    total_topics = sum(c.topics for c in courses)
    completed = sum(c.completed for c in courses)
    return LearningAnalytics(
        courses_enrolled=len(courses), topics_completed=completed, topics_remaining=total_topics - completed,
        lessons_generated=db.scalar(select(func.count()).select_from(Lesson).where(*readable)) or 0,
        quiz_attempts=attempts, average_accuracy=round(earned / possible, 3) if possible else None,
        weak_topics=sorted(weak, key=lambda t: t.last_accuracy or 0), revision_due=due, courses=courses,
        recent_lessons=[RecentLesson(lesson_id=lesson.id, topic_title=topic, course_title=course, depth=lesson.depth,
                                     visibility=lesson.visibility, updated_at=at) for lesson, topic, course, at in recent],
        recent_sessions=[RecentSession(session_id=s.id, title=s.title, course_title=course, updated_at=s.updated_at)
                         for s, course in sessions],
    )
