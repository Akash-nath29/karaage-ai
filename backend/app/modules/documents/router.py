import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import RedirectResponse

from app.config import settings
from app.core.exceptions import AppError
from app.core.permissions import Editor, Viewer
from app.database.session import DbSession
from app.modules.documents import service
from app.modules.documents.models import Document
from app.modules.documents.schemas import DocumentKind, DocumentOut, DocumentStatus, DocumentUpdate

router = APIRouter(tags=["documents"])


@router.post("/workspaces/{workspace_id}/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile,
    access: Editor,
    db: DbSession,
    kind: Annotated[DocumentKind, Form()] = "notes",
    course_id: Annotated[uuid.UUID | None, Form()] = None,
) -> Document:
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)  # ponytail: whole file in memory; stream to storage if limits grow
    if len(data) > limit:
        raise AppError(413, f"The file is larger than {settings.max_upload_mb} MB.")
    return service.upload(db, access, file.filename or "untitled", data, kind, course_id)


@router.get("/workspaces/{workspace_id}/documents", response_model=list[DocumentOut])
def list_documents(workspace_id: uuid.UUID, _: Viewer, db: DbSession, course_id: uuid.UUID | None = None) -> Sequence[Document]:
    return service.list_for_workspace(db, workspace_id, course_id)


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, _: Viewer, db: DbSession) -> Document:
    return service.get(db, document_id)


@router.get("/documents/{document_id}/status", response_model=DocumentStatus)
def get_document_status(document_id: uuid.UUID, _: Viewer, db: DbSession) -> Document:
    return service.get(db, document_id)


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def update_document(document_id: uuid.UUID, data: DocumentUpdate, access: Editor, db: DbSession) -> Document:
    return service.update(db, access, document_id, data)


@router.post("/documents/{document_id}/reprocess", response_model=DocumentOut)
def reprocess_document(document_id: uuid.UUID, access: Editor, db: DbSession) -> Document:
    return service.reprocess(db, access, document_id)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, access: Editor, db: DbSession) -> None:
    service.delete(db, access, document_id)


@router.get("/documents/{document_id}/file", status_code=307)
def open_document(document_id: uuid.UUID, _: Viewer, db: DbSession) -> RedirectResponse:
    # Short-lived signed URL to the private bucket. Browsers keep a #page=N fragment across the redirect.
    return RedirectResponse(service.file_url(db, document_id), status_code=307)
