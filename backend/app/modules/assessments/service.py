"""Question bank (H1–H3), quizzes (H4) and attempts (H5). AI work runs in app.orchestration.assessment_pipeline."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.modules.analytics import service as progress
from app.modules.assessments import grading
from app.modules.assessments.models import (
    AttemptAnswer,
    Question,
    Quiz,
    QuizAttempt,
    QuizQuestion,
)
from app.modules.assessments.schemas import (
    AnswerResult,
    AttemptIn,
    AttemptResults,
    AttemptSummary,
    PaperOut,
    QuestionIn,
    QuestionOut,
    QuestionPatch,
    QuizOut,
    QuizQuestionOut,
    QuizRequest,
)
from app.modules.courses.models import Course
from app.modules.documents.models import Document
from app.modules.jobs import service as jobs
from app.modules.jobs.models import Job
from app.modules.syllabus.models import Topic, Unit

log = logging.getLogger(__name__)
EXTRACT = "extract_questions"


# Module-level so tests can run the work inline instead of going through Redis.
def enqueue_extraction(job_id: uuid.UUID) -> None:
    from app.workers.assessment_tasks import extract_questions

    extract_questions.delay(str(job_id))


def enqueue_quiz(quiz_id: uuid.UUID) -> None:
    from app.workers.assessment_tasks import generate_quiz

    generate_quiz.delay(str(quiz_id))


def enqueue_grading(attempt_id: uuid.UUID) -> None:
    from app.workers.assessment_tasks import grade_attempt

    grade_attempt.delay(str(attempt_id))


def _course(db: Session, course_id: uuid.UUID) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise NotFoundError("Course")
    return course


def _topic_in(db: Session, course_id: uuid.UUID, topic_id: uuid.UUID) -> Topic:
    """The top-level topic (questions and progress live on top-level topics; A2 subtopics roll up)."""
    topic = db.get(Topic, topic_id)
    if topic is None or topic.course_id != course_id:
        raise AppError(422, "That topic isn't in this course.")
    return db.get(Topic, topic.parent_id) or topic if topic.parent_id else topic


# --- Question papers and extraction (H3) ---------------------------------------------------------------------------


def _latest_extraction(db: Session, document_id: uuid.UUID) -> Job | None:
    return db.scalar(select(Job).where(Job.document_id == document_id, Job.kind == EXTRACT)
                     .order_by(Job.created_at.desc()).limit(1))


def request_extraction(db: Session, document_id: uuid.UUID) -> Job:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document")
    if document.course_id is None:
        raise AppError(422, "Assign this paper to a course first: questions are mapped to its syllabus topics.")
    if document.status != "ready":
        raise AppError(409, "Wait until the document has finished processing.")
    latest = _latest_extraction(db, document.id)
    if latest and jobs.is_active(db, latest.id):
        return latest
    job = jobs.create(db, workspace_id=document.workspace_id, kind=EXTRACT, document_id=document.id)
    db.commit()
    try:
        enqueue_extraction(job.id)
    except Exception:
        log.exception("could not enqueue extraction for %s", document.id)
        jobs.fail(db, job, "Could not start: the job queue is unavailable. Try again in a moment.")
        db.commit()
    return job


def extract_after_ingestion(db: Session, document: Document) -> None:
    """A question paper with a course gets its questions extracted as soon as it's indexed (H3)."""
    if document.kind == "question_paper" and document.course_id:
        try:
            request_extraction(db, document.id)
        except AppError as e:
            log.warning("question extraction for %s not started: %s", document.id, e)


def papers(db: Session, course_id: uuid.UUID) -> list[PaperOut]:
    _course(db, course_id)
    extracted = select(Job.document_id).where(Job.kind == EXTRACT)
    docs = db.scalars(select(Document).where(
        Document.course_id == course_id, (Document.kind == "question_paper") | Document.id.in_(extracted)
    ).order_by(Document.created_at))
    counts = dict(db.execute(select(Question.document_id, func.count()).where(Question.course_id == course_id)
                             .group_by(Question.document_id)).all())
    drafts = dict(db.execute(select(Question.document_id, func.count()).where(
        Question.course_id == course_id, Question.status == "draft").group_by(Question.document_id)).all())
    out = []
    for d in docs:
        job = _latest_extraction(db, d.id)
        out.append(PaperOut(document_id=d.id, filename=d.filename, document_status=d.status, job_id=job.id if job else None,
                            status=job.status if job else "none", error=job.error if job else None,
                            questions=counts.get(d.id, 0), drafts=drafts.get(d.id, 0)))
    return out


# --- Question bank ------------------------------------------------------------------------------------------------


def _outs(db: Session, questions: list[Question]) -> list[QuestionOut]:
    topics = {t.id: t for t in db.scalars(select(Topic).where(Topic.id.in_({q.topic_id for q in questions if q.topic_id})))}
    units = {u.id: u for u in db.scalars(select(Unit).where(Unit.id.in_({t.unit_id for t in topics.values()})))}
    docs = dict(db.execute(select(Document.id, Document.filename).where(
        Document.id.in_({q.document_id for q in questions if q.document_id}))).all())
    out = []
    for q in questions:
        topic = topics.get(q.topic_id) if q.topic_id else None
        out.append(QuestionOut.model_validate(q).model_copy(update={
            "topic_title": topic.title if topic else None,
            "unit_title": units[topic.unit_id].title if topic else None,
            "filename": docs.get(q.document_id) if q.document_id else None,
        }))
    return out


def get_question(db: Session, question_id: uuid.UUID) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise NotFoundError("Question")
    return question


def questions(
    db: Session, course_id: uuid.UUID, *, status: str | None = None, topic_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
) -> list[QuestionOut]:
    _course(db, course_id)
    query = select(Question).where(Question.course_id == course_id)
    if status:
        query = query.where(Question.status == status)
    if topic_id:
        query = query.where(Question.topic_id == topic_id)
    if document_id:
        query = query.where(Question.document_id == document_id)
    return _outs(db, list(db.scalars(query.order_by(Question.document_id, Question.source_page, Question.created_at))))


def _checked(type_: str, marks: int, options: list[str], answer: str | None, rubric: list[dict[str, Any]]) -> dict[str, Any]:
    """Options and key that fit the type. A written answer key may be left empty; an objective one must be valid."""
    options = ["True", "False"] if type_ == "true_false" else [o.strip() for o in options if o.strip()] if type_ == "mcq" else []
    if type_ == "mcq" and len(options) < 2:
        raise AppError(422, "A multiple-choice question needs at least two options.")
    if not (answer or "").strip():
        return {"options": options, "answer": None, "rubric": grading.normalize_rubric(rubric, marks) if type_ in grading.WRITTEN else []}
    key, criteria, problem = grading.check_key(type_, options, answer, rubric, marks)
    if problem:
        raise AppError(422, f"Answer key: {problem}.")
    return {"options": options, "answer": key, "rubric": criteria}


def create_question(db: Session, course_id: uuid.UUID, data: QuestionIn) -> QuestionOut:
    course = _course(db, course_id)
    topic = _topic_in(db, course_id, data.topic_id) if data.topic_id else None
    rubric = [c.model_dump() for c in data.rubric]
    question = Question(
        workspace_id=course.workspace_id, course_id=course.id, topic_id=topic.id if topic else None, text=data.text.strip(),
        type=data.type, marks=data.marks, difficulty=data.difficulty, explanation=data.explanation,
        source_kind="manual", status="approved", **_checked(data.type, data.marks, data.options, data.answer, rubric),
    )
    db.add(question)
    db.commit()
    return _outs(db, [question])[0]


def update_question(db: Session, question_id: uuid.UUID, patch: QuestionPatch) -> QuestionOut:
    question = get_question(db, question_id)
    changes = patch.model_dump(exclude_unset=True)
    if "topic_id" in changes:
        question.topic_id = _topic_in(db, question.course_id, patch.topic_id).id if patch.topic_id else None
    for field in ("text", "difficulty", "explanation", "status"):
        if changes.get(field) is not None:
            setattr(question, field, changes[field])
    type_ = patch.type or question.type
    marks = patch.marks or question.marks
    keyed = {"type", "marks", "options", "answer", "rubric"} & changes.keys()
    if keyed:
        options = patch.options if patch.options is not None else question.options
        answer = changes["answer"] if "answer" in changes else question.answer
        if "type" in changes and type_ != question.type and "answer" not in changes:
            answer = None  # a key for another type is meaningless
        rubric = [c.model_dump() for c in patch.rubric] if patch.rubric is not None else question.rubric
        checked = _checked(type_, marks, options, answer, rubric)
        question.type, question.marks = type_, marks
        question.options, question.answer, question.rubric = checked["options"], checked["answer"], checked["rubric"]
    if question.status == "approved" and question.type in grading.OBJECTIVE and question.answer is None:
        raise AppError(422, "Add the answer key before approving an objective question.")
    db.commit()
    return _outs(db, [question])[0]


def delete_question(db: Session, question_id: uuid.UUID) -> None:
    db.delete(get_question(db, question_id))
    db.commit()


# --- Quizzes (H4, A21) --------------------------------------------------------------------------------------------


def scope_topics(db: Session, course_id: uuid.UUID, settings: dict[str, Any]) -> list[Topic]:
    query = select(Topic).where(Topic.course_id == course_id, Topic.parent_id.is_(None))
    if settings.get("topic_ids"):
        query = query.where(Topic.id.in_([uuid.UUID(t) for t in settings["topic_ids"]]))
    elif settings.get("unit_id"):
        query = query.where(Topic.unit_id == uuid.UUID(settings["unit_id"]))
    return list(db.scalars(query.join(Unit, Unit.id == Topic.unit_id).order_by(Unit.ordinal, Topic.ordinal)))


def create_quiz(db: Session, user_id: uuid.UUID, course_id: uuid.UUID, data: QuizRequest, *,
                topic_id: uuid.UUID | None = None) -> QuizOut:
    course = _course(db, course_id)
    if topic_id:
        topic = _topic_in(db, course.id, topic_id)
        topic_ids, title = [topic.id], f"{topic.title} quiz"
    elif data.topic_ids:
        topic_ids = list(dict.fromkeys(_topic_in(db, course.id, t).id for t in data.topic_ids))
        title = f"{course.title}: {len(topic_ids)} topic{'s' if len(topic_ids) > 1 else ''} quiz"
    else:
        topic_ids, title = [], f"{course.title} quiz"
        if data.unit_id:
            unit = db.get(Unit, data.unit_id)
            if unit is None or unit.course_id != course.id:
                raise AppError(422, "That unit isn't in this course.")
            title = f"{unit.title} quiz"
    settings = data.model_dump(mode="json", exclude={"topic_ids"}) | {"topic_ids": [str(t) for t in topic_ids]}
    if not scope_topics(db, course.id, settings):
        raise AppError(409, "This course has no confirmed syllabus topics yet.")
    job = jobs.create(db, workspace_id=course.workspace_id, kind="generate_quiz")
    quiz = Quiz(workspace_id=course.workspace_id, user_id=user_id, course_id=course.id, title=title[:300], settings=settings,
                job_id=job.id)
    db.add(quiz)
    db.commit()
    try:
        enqueue_quiz(quiz.id)
    except Exception:
        log.exception("could not enqueue quiz %s", quiz.id)
        message = "Could not start: the job queue is unavailable. Try again in a moment."
        jobs.fail(db, job, message)
        quiz.status, quiz.error = "failed", message
        db.commit()
    return quiz_detail(db, quiz.id)


def get_quiz(db: Session, quiz_id: uuid.UUID) -> Quiz:
    quiz = db.get(Quiz, quiz_id)
    if quiz is None:
        raise NotFoundError("Quiz")
    return quiz


def _quiz_questions(db: Session, quiz_id: uuid.UUID) -> list[tuple[int, Question]]:
    return [(position, q) for position, q in db.execute(
        select(QuizQuestion.position, Question).join(Question, Question.id == QuizQuestion.question_id)
        .where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.position))]


def _student_view(db: Session, rows: list[tuple[int, Question]]) -> list[QuizQuestionOut]:
    titles = dict(db.execute(select(Topic.id, Topic.title).where(Topic.id.in_({q.topic_id for _, q in rows if q.topic_id}))).all())
    return [QuizQuestionOut(id=q.id, position=p, text=q.text, type=q.type, marks=q.marks, difficulty=q.difficulty,
                            options=q.options, topic_title=titles.get(q.topic_id) if q.topic_id else None) for p, q in rows]


def _attempts(db: Session, quiz_id: uuid.UUID) -> list[AttemptSummary]:
    return [AttemptSummary.model_validate(a) for a in db.scalars(
        select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id).order_by(QuizAttempt.created_at.desc()))]


def quiz_detail(db: Session, quiz_id: uuid.UUID) -> QuizOut:
    quiz = get_quiz(db, quiz_id)
    return QuizOut.model_validate(quiz).model_copy(update={
        "questions": _student_view(db, _quiz_questions(db, quiz.id)), "attempts": _attempts(db, quiz.id)})


def course_quizzes(db: Session, course_id: uuid.UUID, user_id: uuid.UUID) -> list[QuizOut]:
    """Your quizzes in this course (they're private)."""
    _course(db, course_id)
    return [QuizOut.model_validate(q).model_copy(update={"attempts": _attempts(db, q.id)})
            for q in db.scalars(select(Quiz).where(Quiz.course_id == course_id, Quiz.user_id == user_id)
                                .order_by(Quiz.created_at.desc()))]


def delete_quiz(db: Session, quiz_id: uuid.UUID) -> None:
    db.delete(get_quiz(db, quiz_id))
    db.commit()


# --- Attempts and results (H5) -------------------------------------------------------------------------------------


def get_attempt(db: Session, attempt_id: uuid.UUID) -> QuizAttempt:
    attempt = db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise NotFoundError("Attempt")
    return attempt


def submit(db: Session, quiz_id: uuid.UUID, data: AttemptIn) -> AttemptSummary:
    """Objective answers are graded now; written ones go to one AI grading job. Blank answers score 0."""
    quiz = get_quiz(db, quiz_id)
    if quiz.status != "ready":
        raise AppError(409, "This quiz isn't ready yet.")
    rows = _quiz_questions(db, quiz.id)
    known = {q.id for _, q in rows}
    if unknown := {a.question_id for a in data.answers} - known:
        raise AppError(422, f"{len(unknown)} answer(s) are for questions that aren't in this quiz.")
    given = {a.question_id: a.answer.strip() for a in data.answers}
    attempt = QuizAttempt(id=uuid.uuid4(), quiz_id=quiz.id, max_score=sum(q.marks for _, q in rows))
    db.add(attempt)
    db.flush()  # no ORM relationships: the attempt row must exist before its answers
    for position, q in rows:
        answer = AttemptAnswer(attempt_id=attempt.id, question_id=q.id, position=position, answer=given.get(q.id, ""),
                               max_score=q.marks, feedback={})
        if q.type in grading.OBJECTIVE:
            correct = q.answer is not None and grading.grade_objective(q.type, q.answer, answer.answer)
            answer.score, answer.graded_by = (q.marks if correct else 0), "auto"
        elif not answer.answer:
            answer.score, answer.graded_by, answer.feedback = 0, "auto", {"note": "No answer given."}
        db.add(answer)
    db.flush()
    pending = db.scalar(select(func.count()).select_from(AttemptAnswer).where(
        AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.score.is_(None)))
    if pending:
        _queue_grading(db, attempt)
    else:
        finish_attempt(db, attempt)
        db.commit()
    return AttemptSummary.model_validate(attempt)


def _queue_grading(db: Session, attempt: QuizAttempt) -> None:
    quiz = get_quiz(db, attempt.quiz_id)
    job = jobs.create(db, workspace_id=quiz.workspace_id, kind="grade_attempt")
    attempt.status, attempt.job_id, attempt.error = "grading", job.id, None
    db.commit()
    try:
        enqueue_grading(attempt.id)
    except Exception:
        log.exception("could not enqueue grading for %s", attempt.id)
        message = "Could not start grading: the job queue is unavailable. Use “Grade again” in a moment."
        jobs.fail(db, job, message)
        attempt.status, attempt.error = "failed", message
        db.commit()


def regrade(db: Session, attempt_id: uuid.UUID) -> AttemptSummary:
    """Retry AI grading for answers that aren't graded yet (after a failed grading job)."""
    attempt = get_attempt(db, attempt_id)
    if attempt.status == "graded" or (attempt.status == "grading" and jobs.is_active(db, attempt.job_id)):
        raise AppError(409, "This attempt is already graded or being graded.")
    _queue_grading(db, attempt)
    return AttemptSummary.model_validate(attempt)


def finish_attempt(db: Session, attempt: QuizAttempt) -> None:
    """Totals, status, and topic progress (Workflow 6 step 7). The caller commits."""
    answers = list(db.scalars(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)))
    attempt.score = sum(a.score or 0 for a in answers)
    attempt.status, attempt.graded_at, attempt.error = "graded", datetime.now(UTC), None
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_([a.question_id for a in answers])))}
    quiz = get_quiz(db, attempt.quiz_id)
    progress.record_attempt(db, quiz.user_id, [(questions[a.question_id], a.score or 0, a.max_score) for a in answers])


def results(db: Session, attempt_id: uuid.UUID) -> AttemptResults:
    attempt = get_attempt(db, attempt_id)
    quiz = get_quiz(db, attempt.quiz_id)
    rows = _quiz_questions(db, quiz.id)
    views = {v.id: v for v in _student_view(db, rows)}
    by_question = {q.id: q for _, q in rows}
    out = []
    for a in db.scalars(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id).order_by(AttemptAnswer.position)):
        q = by_question.get(a.question_id)
        if q is None:  # removed from the quiz since
            continue
        reference = q.options[int(q.answer)] if q.type in ("mcq", "true_false") and q.answer is not None else q.answer
        out.append(AnswerResult(
            question=views[q.id], answer=a.answer, score=a.score, max_score=a.max_score, graded_by=a.graded_by,
            correct=(a.score == a.max_score) if q.type in grading.OBJECTIVE and a.score is not None else None,
            feedback=a.feedback, reference_answer=reference, explanation=q.explanation,
        ))
    return AttemptResults(attempt=AttemptSummary.model_validate(attempt), quiz_id=quiz.id, quiz_title=quiz.title,
                          course_id=quiz.course_id, answers=out)
