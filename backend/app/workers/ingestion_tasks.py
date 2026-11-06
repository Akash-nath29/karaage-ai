import uuid

from app.database.session import SessionLocal
from app.modules.documents import ingestion
from app.modules.syllabus import parsing
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def ingest_document(self, job_id: str) -> None:  # type: ignore[no-untyped-def]  # celery's bound self
    with SessionLocal() as db:
        retry = ingestion.run(db, uuid.UUID(job_id), can_retry=self.request.retries < self.max_retries)
    if retry:
        raise self.retry(countdown=60 * 2**self.request.retries)  # 1, 2, 4 minutes


@celery_app.task(bind=True, max_retries=3)
def parse_syllabus(self, job_id: str) -> None:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        retry = parsing.run(db, uuid.UUID(job_id), can_retry=self.request.retries < self.max_retries)
    if retry:
        raise self.retry(countdown=60 * 2**self.request.retries)
