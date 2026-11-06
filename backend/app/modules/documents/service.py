import hashlib
import logging
import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core import storage
from app.core.exceptions import AppError, NotFoundError
from app.core.permissions import Access
from app.modules.courses import service as courses
from app.modules.documents import repository
from app.modules.documents.extraction import CONTENT_TYPES, sniff
from app.modules.documents.models import Document
from app.modules.documents.schemas import DocumentUpdate
from app.modules.jobs import service as jobs
from app.modules.lessons import service as lessons
from app.modules.rag import repository as chunks
from app.modules.syllabus import mapping
from app.modules.users.service import audit
from app.modules.workspaces import service as workspaces

log = logging.getLogger(__name__)


def enqueue_ingestion(job_id: uuid.UUID) -> None:
    # Module-level so tests can run the pipeline inline instead of going through Redis.
    from app.workers.ingestion_tasks import ingest_document

    ingest_document.delay(str(job_id))


def _check_course(db: Session, workspace_id: uuid.UUID, course_id: uuid.UUID) -> None:
    if courses.get(db, course_id).workspace_id != workspace_id:
        raise AppError(422, "That course belongs to a different workspace.")


def _queue(db: Session, document: Document) -> None:
    job = jobs.create(db, workspace_id=document.workspace_id, kind="ingest_document", document_id=document.id)
    document.job_id, document.status, document.error = job.id, "queued", None
    db.commit()
    try:
        enqueue_ingestion(job.id)
    except Exception:
        log.exception("could not enqueue ingestion job %s", job.id)
        message = "Could not start processing: the job queue is unavailable. Try Reprocess in a moment."
        jobs.fail(db, job, message)
        document.status, document.error = "failed", message
        db.commit()


def list_for_workspace(db: Session, workspace_id: uuid.UUID, course_id: uuid.UUID | None) -> Sequence[Document]:
    workspaces.get(db, workspace_id)
    return repository.list_for_workspace(db, workspace_id, course_id)


def get(db: Session, document_id: uuid.UUID) -> Document:
    document = repository.get(db, document_id)
    if document is None:
        raise NotFoundError("Document")
    return document


def upload(
    db: Session, access: Access, filename: str, data: bytes, kind: str, course_id: uuid.UUID | None
) -> Document:
    """PRD D3 steps 1–5: validate, checksum, store original, create record, queue ingestion."""
    workspace_id = access.workspace_id
    if course_id:
        _check_course(db, workspace_id, course_id)
    if not data:
        raise AppError(422, "The file is empty.")
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1][:255] or "untitled"
    file_type = sniff(data, filename)
    if file_type is None:
        raise AppError(415, "Unsupported file. Upload a PDF, Word (.docx), PowerPoint (.pptx), text, Markdown, PNG or JPEG file.")
    checksum = hashlib.sha256(data).hexdigest()
    if existing := repository.find_by_checksum(db, workspace_id, checksum):
        raise AppError(409, f"This file is already in the workspace as “{existing.filename}”.")

    document = Document(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        course_id=course_id,
        kind=kind,
        filename=filename,
        file_type=file_type,
        size_bytes=len(data),
        checksum=checksum,
        uploaded_by=access.user.id,
    )
    document.storage_key = f"documents/{document.id}"
    storage.put(document.storage_key, data, CONTENT_TYPES[file_type])  # before the row: no row without a file
    repository.add(db, document)
    _queue(db, document)
    return document


def owned(db: Session, access: Access, document_id: uuid.UUID) -> Document:
    """A11: editors may change or delete their own uploads; admins and the owner, any."""
    document = get(db, document_id)
    if not access.at_least("admin") and document.uploaded_by != access.user.id:
        raise AppError(403, "Editors can only change or delete documents they uploaded.")
    return document


def update(db: Session, access: Access, document_id: uuid.UUID, data: DocumentUpdate) -> Document:
    document = owned(db, access, document_id)
    affected = {document.course_id}
    if "course_id" in data.model_fields_set:
        if data.course_id:
            _check_course(db, document.workspace_id, data.course_id)
        document.course_id = data.course_id
        chunks.set_course(db, document.id, data.course_id)
    if data.kind:
        document.kind = data.kind  # to/from "syllabus" changes whether it counts as topic material
    for course_id in (affected | {document.course_id}) - {None}:
        mapping.remap_quietly(db, course_id)  # type: ignore[arg-type]  # None removed above
    db.commit()
    return document


def reprocess(db: Session, access: Access, document_id: uuid.UUID) -> Document:
    document = owned(db, access, document_id)
    if document.status in ("queued", "processing") and jobs.is_active(db, document.job_id):
        raise AppError(409, "This document is already being processed.")
    _queue(db, document)
    return document


def delete(db: Session, access: Access, document_id: uuid.UUID) -> None:
    document = owned(db, access, document_id)
    key = document.storage_key
    audit(db, "document.deleted", user_id=access.user.id, workspace_id=document.workspace_id, target=document.filename)
    lessons.flag_document_changed(db, document.id, "A document this lesson cites was deleted.")
    repository.delete(db, document)  # chunks and jobs cascade: gone from retrieval at commit (PRD §10.5)
    db.commit()
    try:
        storage.delete(key)
    except Exception:
        log.warning("document %s deleted but its stored file %s could not be removed", document_id, key)


def file_url(db: Session, document_id: uuid.UUID) -> str:
    document = get(db, document_id)
    return storage.presigned_url(document.storage_key, document.filename)
