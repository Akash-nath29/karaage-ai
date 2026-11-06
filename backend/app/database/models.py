"""Imports every model so Base.metadata is complete (Alembic autogenerate, workers resolving foreign keys)."""

from app.ai.usage import LlmUsage
from app.modules.analytics.models import TopicProgress
from app.modules.assessments.models import (
    AttemptAnswer,
    Question,
    Quiz,
    QuizAttempt,
    QuizQuestion,
)
from app.modules.courses.models import Course
from app.modules.documents.models import Document
from app.modules.jobs.models import Job, JobEvent
from app.modules.lessons.models import (
    Lesson,
    LessonCitation,
    LessonFeedback,
    LessonVersion,
)
from app.modules.rag.models import DocumentChunk
from app.modules.research.models import ResearchJob, ResearchSource
from app.modules.syllabus.models import DocumentTopic, Syllabus, Topic, Unit
from app.modules.tutor.models import TutorMessage, TutorSession
from app.modules.users.models import AuditLog, EmailToken, RefreshToken, User
from app.modules.workspaces.models import Invitation, Workspace, WorkspaceMember

__all__ = [
    "AttemptAnswer", "AuditLog", "EmailToken", "Invitation", "RefreshToken", "User", "WorkspaceMember", "Course", "Document", "DocumentChunk", "DocumentTopic", "Job", "JobEvent", "Lesson",
    "LessonCitation", "LessonFeedback", "LessonVersion", "LlmUsage", "Question", "Quiz", "QuizAttempt", "QuizQuestion",
    "ResearchJob", "ResearchSource", "Syllabus", "Topic", "TopicProgress", "TutorMessage", "TutorSession", "Unit",
    "Workspace",
]
