import uuid
from typing import Literal

from fastapi import APIRouter

from app.core.permissions import Editor, Viewer
from app.database.session import DbSession
from app.modules.assessments import service
from app.modules.assessments.schemas import (
    AttemptIn,
    AttemptResults,
    AttemptSummary,
    PaperOut,
    QuestionIn,
    QuestionOut,
    QuestionPatch,
    QuizOut,
    QuizRequest,
)
from app.modules.jobs.models import Job
from app.modules.jobs.schemas import JobOut
from app.modules.syllabus.service import get_topic

router = APIRouter(tags=["assessments"])


@router.post("/documents/{document_id}/questions/extract", response_model=JobOut, status_code=202)
def extract_questions(document_id: uuid.UUID, _: Editor, db: DbSession) -> Job:
    """Extract a paper's questions as drafts for review (H3). Runs on its own after a question paper is indexed."""
    return service.request_extraction(db, document_id)


@router.get("/courses/{course_id}/question-papers", response_model=list[PaperOut])
def question_papers(course_id: uuid.UUID, _: Viewer, db: DbSession) -> list[PaperOut]:
    return service.papers(db, course_id)


@router.get("/courses/{course_id}/questions", response_model=list[QuestionOut])
def list_questions(
    course_id: uuid.UUID, _: Editor, db: DbSession, status: Literal["draft", "approved"] | None = None,
    topic_id: uuid.UUID | None = None, document_id: uuid.UUID | None = None,
) -> list[QuestionOut]:
    """Editors and above: the bank holds answer keys, which students only see after an attempt (D32)."""
    return service.questions(db, course_id, status=status, topic_id=topic_id, document_id=document_id)


@router.post("/courses/{course_id}/questions", response_model=QuestionOut, status_code=201)
def create_question(course_id: uuid.UUID, data: QuestionIn, _: Editor, db: DbSession) -> QuestionOut:
    return service.create_question(db, course_id, data)


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: uuid.UUID, data: QuestionPatch, _: Editor, db: DbSession) -> QuestionOut:
    return service.update_question(db, question_id, data)


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: uuid.UUID, _: Editor, db: DbSession) -> None:
    service.delete_question(db, question_id)


@router.post("/topics/{topic_id}/quizzes", response_model=QuizOut, status_code=202)
def topic_quiz(topic_id: uuid.UUID, access: Viewer, db: DbSession, data: QuizRequest | None = None) -> QuizOut:
    return service.create_quiz(db, access.user.id, get_topic(db, topic_id).course_id, data or QuizRequest(), topic_id=topic_id)


@router.post("/courses/{course_id}/quizzes", response_model=QuizOut, status_code=202)
def course_quiz(course_id: uuid.UUID, access: Viewer, db: DbSession, data: QuizRequest | None = None) -> QuizOut:
    """A quiz over the whole course, one unit, or chosen topics (A21)."""
    return service.create_quiz(db, access.user.id, course_id, data or QuizRequest())


@router.get("/courses/{course_id}/quizzes", response_model=list[QuizOut])
def course_quizzes(course_id: uuid.UUID, access: Viewer, db: DbSession) -> list[QuizOut]:
    return service.course_quizzes(db, course_id, access.user.id)


@router.get("/quizzes/{quiz_id}", response_model=QuizOut)
def get_quiz(quiz_id: uuid.UUID, _: Viewer, db: DbSession) -> QuizOut:
    """Questions without their answer keys, plus past attempts."""
    return service.quiz_detail(db, quiz_id)


@router.delete("/quizzes/{quiz_id}", status_code=204)
def delete_quiz(quiz_id: uuid.UUID, _: Viewer, db: DbSession) -> None:
    service.delete_quiz(db, quiz_id)


@router.post("/quizzes/{quiz_id}/attempts", response_model=AttemptSummary, status_code=201)
def submit_attempt(quiz_id: uuid.UUID, data: AttemptIn, _: Viewer, db: DbSession) -> AttemptSummary:
    """Objective answers are graded at once; written ones by an AI grading job (status "grading")."""
    return service.submit(db, quiz_id, data)


@router.get("/attempts/{attempt_id}/results", response_model=AttemptResults)
def attempt_results(attempt_id: uuid.UUID, _: Viewer, db: DbSession) -> AttemptResults:
    return service.results(db, attempt_id)


@router.post("/attempts/{attempt_id}/grade", response_model=AttemptSummary, status_code=202)
def regrade_attempt(attempt_id: uuid.UUID, _: Viewer, db: DbSession) -> AttemptSummary:
    return service.regrade(db, attempt_id)
