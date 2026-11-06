import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.ai import usage
from app.core.permissions import CurrentUser, Viewer
from app.database.session import DbSession
from app.modules.analytics import service
from app.modules.analytics.service import CourseProgress, LearningAnalytics, TopicProgressOut
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember

router = APIRouter(tags=["progress"])


class StudiedIn(BaseModel):
    studied: bool


@router.get("/courses/{course_id}/progress", response_model=CourseProgress)
def course_progress(course_id: uuid.UUID, access: Viewer, db: DbSession) -> CourseProgress:
    """Your progress (§I: per user)."""
    return service.course_progress(db, course_id, access.user.id)


@router.put("/topics/{topic_id}/progress", response_model=TopicProgressOut)
def mark_studied(topic_id: uuid.UUID, data: StudiedIn, access: Viewer, db: DbSession) -> TopicProgressOut:
    """"Mark studied" (A14); quizzes update the rest."""
    return service.set_studied(db, access.user.id, topic_id, data.studied)


@router.get("/users/me/learning-analytics", response_model=LearningAnalytics)
def learning_analytics(user: CurrentUser, db: DbSession) -> LearningAnalytics:
    """Your dashboard (Module I, Screen 1) across every workspace you're in."""
    return service.learning_analytics(db, user.id)


@router.get("/workspaces/{workspace_id}/usage", response_model=usage.WorkspaceUsage)
def workspace_usage(workspace_id: uuid.UUID, access: Viewer, db: DbSession) -> usage.WorkspaceUsage:
    """This month's AI usage against the budget. Admins and the owner also see it per member."""
    members = dict(db.execute(select(User.id, User.display_name).join(WorkspaceMember, WorkspaceMember.user_id == User.id)
                              .where(WorkspaceMember.workspace_id == workspace_id)).all()) if access.at_least("admin") else None
    return usage.workspace_usage(db, workspace_id, members=members)


@router.get("/users/me/usage", response_model=usage.MyUsage)
def my_usage(user: CurrentUser, db: DbSession) -> usage.MyUsage:
    names = dict(db.execute(select(Workspace.id, Workspace.name).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
                            .where(WorkspaceMember.user_id == user.id)).all())
    return usage.my_usage(db, user.id, names)
