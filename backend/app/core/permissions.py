"""Who may do what (PRD §4, docs/decisions.md A11).

Every protected route declares a minimum role (`Viewer`, `Editor`, `Admin`, `Owner`). The workspace comes from
the resource id in the path (or query), so a route can't forget to scope by it. Non-members get 404 (a private
workspace's resources don't exist for them, Workflow 7); members below the role get 403. Personal resources
(tutor sessions, quizzes and their attempts, private lessons) are 404 for everyone but their owner.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.exceptions import AppError, NotFoundError
from app.database.session import DbSession, row_security
from app.modules.assessments.models import Question, Quiz, QuizAttempt
from app.modules.courses.models import Course
from app.modules.documents.models import Document
from app.modules.jobs.models import Job
from app.modules.lessons.models import Lesson
from app.modules.research.models import ResearchJob
from app.modules.syllabus.models import Topic
from app.modules.tutor.models import TutorSession
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember

ROLES = ("viewer", "editor", "admin", "owner")

# Path/query parameter → resource name in "not found" messages. The first one present decides the workspace.
RESOURCES = {
    "workspace_id": "Workspace", "course_id": "Course", "topic_id": "Topic", "document_id": "Document",
    "lesson_id": "Lesson", "research_id": "Research", "quiz_id": "Quiz", "attempt_id": "Attempt",
    "question_id": "Question", "session_id": "Tutor session", "job_id": "Job",
}
_MODELS: dict[str, Any] = {"course_id": Course, "document_id": Document, "research_id": ResearchJob, "quiz_id": Quiz,
                           "question_id": Question, "session_id": TutorSession, "job_id": Job}


@dataclass
class Access:
    user: User
    workspace_id: uuid.UUID
    role: str

    def at_least(self, role: str) -> bool:
        return ROLES.index(self.role) >= ROLES.index(role)


def act_as(db: Session, user_id: uuid.UUID) -> None:
    """Attribute this session's work to a user (usage, jobs) and turn on row-level security for them (D27).
    `database.session` re-applies the setting at the start of every later transaction."""
    db.info["user_id"], db.info["rls"] = user_id, True
    row_security(db.connection(), user_id)


def current_user(request: Request, db: DbSession) -> User:
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else request.cookies.get("access_token", "")
    user_id = security.read_access_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise AppError(401, "Sign in to continue.")
    act_as(db, user.id)
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def role_of(db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID) -> str | None:
    return db.scalar(select(WorkspaceMember.role).where(
        WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id))


def _locate(db: Session, name: str, value: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID | None] | None:
    """(workspace, owner if the resource is personal) of the resource a parameter names, or None."""
    if name == "workspace_id":
        return (value, None) if db.get(Workspace, value) else None
    if name == "topic_id":
        topic = db.get(Topic, value)
        course = db.get(Course, topic.course_id) if topic else None
        return (course.workspace_id, None) if course else None
    if name == "attempt_id":
        attempt = db.get(QuizAttempt, value)
        quiz = db.get(Quiz, attempt.quiz_id) if attempt else None
        return (quiz.workspace_id, quiz.user_id) if quiz else None
    if name == "lesson_id":
        lesson = db.get(Lesson, value)
        return (lesson.workspace_id, lesson.owner_id if lesson.visibility == "private" else None) if lesson else None
    model = _MODELS[name]
    row = db.get(model, value)
    return (row.workspace_id, row.user_id if model in (TutorSession, Quiz) else None) if row else None


def check(db: Session, user: User, workspace_id: uuid.UUID, min_role: str, resource: str = "Workspace",
          owner_id: uuid.UUID | None = None) -> Access:
    role = role_of(db, user.id, workspace_id)
    if role is None or (owner_id and owner_id != user.id):
        raise NotFoundError(resource)
    if ROLES.index(role) < ROLES.index(min_role):
        raise AppError(403, f"This needs the {min_role} role or higher in this workspace (you're a {role}).")
    return Access(user, workspace_id, role)


def allow(min_role: str):  # type: ignore[no-untyped-def]
    def authorize(request: Request, db: DbSession, user: CurrentUser) -> Access:
        name = next((n for n in RESOURCES if n in request.path_params), None) or next(
            (n for n in RESOURCES if n in request.query_params), None)
        if name is None:
            raise RuntimeError(f"{request.url.path}: no resource id to authorize against")
        raw = request.path_params.get(name) or request.query_params.get(name)
        try:
            value = uuid.UUID(raw)
        except ValueError:
            raise AppError(422, f"{name} is not a valid id") from None
        found = _locate(db, name, value)
        if found is None:
            raise NotFoundError(RESOURCES[name])
        return check(db, user, found[0], min_role, RESOURCES[name], found[1])

    return Depends(authorize)


Viewer = Annotated[Access, allow("viewer")]
Editor = Annotated[Access, allow("editor")]
Admin = Annotated[Access, allow("admin")]
Owner = Annotated[Access, allow("owner")]
