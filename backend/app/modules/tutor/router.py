import uuid
from collections.abc import Sequence

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.permissions import CurrentUser, Viewer
from app.database.session import DbSession, SessionFactory
from app.modules.tutor import service
from app.modules.tutor.models import TutorMessage
from app.modules.tutor.schemas import MessageIn, MessageOut, SessionIn, SessionOut
from app.orchestration import tutor_pipeline

router = APIRouter(prefix="/tutor", tags=["tutor"])


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(data: SessionIn, user: CurrentUser, db: DbSession) -> SessionOut:
    return service.out(db, service.create(db, user, data))


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    workspace_id: uuid.UUID, access: Viewer, db: DbSession, course_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
) -> list[SessionOut]:
    """Your own conversations in a workspace."""
    return service.list_sessions(db, access.user.id, workspace_id, course_id, topic_id)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: uuid.UUID, _: Viewer, db: DbSession) -> SessionOut:
    return service.out(db, service.get(db, session_id))


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: uuid.UUID, _: Viewer, db: DbSession) -> None:
    service.delete(db, session_id)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(session_id: uuid.UUID, _: Viewer, db: DbSession) -> Sequence[TutorMessage]:
    return service.messages(db, session_id)


@router.post("/sessions/{session_id}/messages")
def send_message(session_id: uuid.UUID, data: MessageIn, _: Viewer, db: DbSession, sessions: SessionFactory) -> StreamingResponse:
    """Ask the tutor. Server-Sent Events: `status`, `token` (answer text), then `done` with the saved answer, or
    `error` followed by `done`. 404/422/429 come back as plain errors before the stream opens."""
    question = service.add_question(db, session_id, data)
    return StreamingResponse(
        tutor_pipeline.answer(sessions, question.id, data.web),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
