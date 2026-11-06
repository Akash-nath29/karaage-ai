import uuid

from fastapi import APIRouter

from app.core.permissions import Viewer
from app.database.session import DbSession
from app.modules.rag import service
from app.modules.rag.schemas import Passage, SearchRequest

router = APIRouter(tags=["retrieval"])


@router.post("/workspaces/{workspace_id}/search", response_model=list[Passage])
def search(workspace_id: uuid.UUID, request: SearchRequest, _: Viewer, db: DbSession) -> list[Passage]:
    return service.search(db, workspace_id, request)
