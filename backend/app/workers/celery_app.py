import sentry_sdk
from celery import Celery

import app.database.models  # noqa: F401  full metadata so foreign keys resolve
from app.config import settings

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn)  # its Celery integration switches on by itself (D33)

celery_app = Celery("semsaviour", broker=settings.redis_url, include=["app.workers.ingestion_tasks", "app.workers.research_tasks", "app.workers.generation_tasks", "app.workers.assessment_tasks"])
celery_app.conf.update(
    task_ignore_result=True,  # status lives in the jobs table
    task_acks_late=True,  # a crashed worker's job is redelivered; ingestion is idempotent
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
