import uuid
from typing import Annotated

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse

from app.core.permissions import Viewer
from app.database.session import DbSession, SessionFactory
from app.modules.jobs import service
from app.modules.jobs.models import Job
from app.modules.jobs.schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, _: Viewer, db: DbSession) -> Job:
    return service.get(db, job_id)


@router.get("/{job_id}/events")
def stream_job_events(
    job_id: uuid.UUID, _: Viewer, db: DbSession, sessions: SessionFactory, last_event_id: Annotated[int, Header()] = 0
) -> StreamingResponse:
    return StreamingResponse(
        service.event_stream(sessions, job_id, last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
