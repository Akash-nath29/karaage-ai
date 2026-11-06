import uuid

from app.database.session import SessionLocal
from app.orchestration import lesson_pipeline
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def generate_lesson(self, lesson_id: str, request: str | None = None) -> None:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        retry = lesson_pipeline.run(
            db, uuid.UUID(lesson_id), request=request, can_retry=self.request.retries < self.max_retries
        )
    if retry:
        raise self.retry(countdown=60 * 2**self.request.retries)
