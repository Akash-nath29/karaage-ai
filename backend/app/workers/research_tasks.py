import uuid

from app.database.session import SessionLocal
from app.orchestration import research_pipeline
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def run_research(self, research_id: str) -> None:  # type: ignore[no-untyped-def]  # celery's bound self
    with SessionLocal() as db:
        retry = research_pipeline.run(db, uuid.UUID(research_id), can_retry=self.request.retries < self.max_retries)
    if retry:
        raise self.retry(countdown=60 * 2**self.request.retries)
