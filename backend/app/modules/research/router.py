import uuid
from collections.abc import Sequence

from fastapi import APIRouter

from app.core.permissions import Viewer
from app.database.session import DbSession
from app.modules.research import service
from app.modules.research.models import ResearchJob, ResearchSource
from app.modules.research.schemas import ResearchOut, ResearchRequest, ResearchSourceOut

router = APIRouter(tags=["research"])


@router.post("/topics/{topic_id}/research", response_model=ResearchOut, status_code=202)
def request_research(topic_id: uuid.UUID, _: Viewer, db: DbSession, data: ResearchRequest | None = None) -> ResearchJob:
    """Research a topic on the web. Returns a running or recent run instead of starting a new one, unless refresh."""
    return service.request(db, topic_id, refresh=bool(data and data.refresh))


@router.get("/topics/{topic_id}/research", response_model=ResearchOut | None)
def latest_research(topic_id: uuid.UUID, _: Viewer, db: DbSession) -> ResearchJob | None:
    return service.latest_for_topic(db, topic_id)


@router.get("/research/{research_id}", response_model=ResearchOut)
def get_research(research_id: uuid.UUID, _: Viewer, db: DbSession) -> ResearchJob:
    return service.get(db, research_id)


@router.get("/research/{research_id}/sources", response_model=list[ResearchSourceOut])
def research_sources(research_id: uuid.UUID, _: Viewer, db: DbSession) -> Sequence[ResearchSource]:
    return service.sources(db, research_id)


@router.post("/research/{research_id}/refresh", response_model=ResearchOut, status_code=202)
def refresh_research(research_id: uuid.UUID, _: Viewer, db: DbSession) -> ResearchJob:
    return service.refresh(db, research_id)
