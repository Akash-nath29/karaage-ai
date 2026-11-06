import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import usage
from app.core import permissions
from app.core.exceptions import AppError, NotFoundError
from app.modules.courses.models import Course
from app.modules.lessons import service as lessons
from app.modules.syllabus.models import Topic
from app.modules.tutor.models import TutorMessage, TutorSession
from app.modules.tutor.schemas import MessageIn, SessionIn, SessionOut
from app.modules.users.models import User
from app.modules.workspaces import service as workspaces

DEFAULT_TITLE = "New conversation"


def get(db: Session, session_id: uuid.UUID) -> TutorSession:
    tutor = db.get(TutorSession, session_id)
    if tutor is None:
        raise NotFoundError("Tutor session")
    return tutor


def out(db: Session, tutor: TutorSession) -> SessionOut:
    course = db.get(Course, tutor.course_id) if tutor.course_id else None
    topic = db.get(Topic, tutor.topic_id) if tutor.topic_id else None
    return SessionOut.model_validate(tutor).model_copy(
        update={"course_title": course.title if course else None, "topic_title": topic.title if topic else None}
    )


def create(db: Session, user: User, data: SessionIn) -> TutorSession:
    course_id, topic_id = data.course_id, data.topic_id
    lesson = lessons.get(db, data.lesson_id) if data.lesson_id else None
    if lesson:
        if topic_id and topic_id != lesson.topic_id:
            raise AppError(422, "That lesson belongs to another topic.")
        topic_id = lesson.topic_id
    if topic_id:
        topic = db.get(Topic, topic_id)
        if topic is None:
            raise NotFoundError("Topic")
        if course_id and course_id != topic.course_id:
            raise AppError(422, "That topic belongs to another course.")
        course_id = topic.course_id
    workspace_id = data.workspace_id
    if course_id:
        course = db.get(Course, course_id)
        if course is None:
            raise NotFoundError("Course")
        if workspace_id and course.workspace_id != workspace_id:
            raise AppError(422, "That course belongs to another workspace.")
        workspace_id = course.workspace_id
    if workspace_id is None:
        raise AppError(422, "Give a workspace, course, topic or lesson for the conversation.")
    workspaces.get(db, workspace_id)
    permissions.check(db, user, workspace_id, "viewer", "Workspace")
    if lesson and lesson.visibility == "private" and lesson.owner_id != user.id:
        raise NotFoundError("Lesson")
    tutor = TutorSession(workspace_id=workspace_id, user_id=user.id, course_id=course_id, topic_id=topic_id,
                         lesson_id=data.lesson_id, mode=data.mode, title=data.title or DEFAULT_TITLE)
    db.add(tutor)
    db.commit()
    return tutor


def list_sessions(
    db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID, course_id: uuid.UUID | None, topic_id: uuid.UUID | None
) -> list[SessionOut]:
    """Your conversations only: they're private (§4.3)."""
    query = select(TutorSession).where(TutorSession.workspace_id == workspace_id, TutorSession.user_id == user_id)
    if course_id:
        query = query.where(TutorSession.course_id == course_id)
    if topic_id:
        query = query.where(TutorSession.topic_id == topic_id)
    return [out(db, s) for s in db.scalars(query.order_by(TutorSession.updated_at.desc()))]


def delete(db: Session, session_id: uuid.UUID) -> None:
    db.delete(get(db, session_id))
    db.commit()


def messages(db: Session, session_id: uuid.UUID) -> Sequence[TutorMessage]:
    get(db, session_id)
    return db.scalars(select(TutorMessage).where(TutorMessage.session_id == session_id).order_by(TutorMessage.created_at)).all()


def add_question(db: Session, session_id: uuid.UUID, data: MessageIn) -> TutorMessage:
    """Save the student's message before answering, so it's never lost. Budget is checked here, before the
    stream opens, so the client gets a normal 429 instead of an error event."""
    tutor = get(db, session_id)
    usage.check_budget(db, tutor.workspace_id, searches=1 if data.web else 0)
    tutor.mode = data.mode or tutor.mode
    if tutor.title == DEFAULT_TITLE:
        first_line = data.content.strip().splitlines()[0]
        tutor.title = first_line[:80] + ("…" if len(first_line) > 80 else "")
    tutor.updated_at = datetime.now(UTC)
    message = TutorMessage(session_id=tutor.id, role="user", mode=tutor.mode, content=data.content.strip())
    db.add(message)
    db.commit()
    return message
