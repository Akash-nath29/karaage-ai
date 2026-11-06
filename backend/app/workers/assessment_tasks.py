import uuid

from app.database.session import SessionLocal
from app.orchestration import assessment_pipeline
from app.workers.celery_app import celery_app


def _run(task, work, item_id: str) -> None:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        retry = work(db, uuid.UUID(item_id), can_retry=task.request.retries < task.max_retries)
    if retry:
        raise task.retry(countdown=60 * 2**task.request.retries)


@celery_app.task(bind=True, max_retries=3)
def extract_questions(self, job_id: str) -> None:  # type: ignore[no-untyped-def]
    _run(self, assessment_pipeline.run_extraction, job_id)


@celery_app.task(bind=True, max_retries=3)
def generate_quiz(self, quiz_id: str) -> None:  # type: ignore[no-untyped-def]
    _run(self, assessment_pipeline.run_quiz, quiz_id)


@celery_app.task(bind=True, max_retries=3)
def grade_attempt(self, attempt_id: str) -> None:  # type: ignore[no-untyped-def]
    _run(self, assessment_pipeline.run_grading, attempt_id)
