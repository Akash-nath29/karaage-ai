"""Ingestion pipeline (PRD D3 steps 6–12): extract → chunk → embed (cached) → store.

Idempotent per document: a re-run replaces the document's chunks in one transaction, so a crash, a retry or a
reprocess never leaves the document half-indexed. Unchanged chunks reuse their embeddings.
"""

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from pathlib import PurePath

from sqlalchemy.orm import Session

from app.ai import providers, usage
from app.ai.providers.base import token_batches
from app.config import settings
from app.core import storage
from app.core.tokens import estimate_tokens
from app.modules.assessments import service as assessments
from app.modules.documents import chunking, extraction
from app.modules.documents import repository as documents
from app.modules.documents.models import Document
from app.modules.jobs import repository as job_repository
from app.modules.jobs import service as jobs
from app.modules.jobs.models import Job
from app.modules.lessons import service as lessons
from app.modules.rag import repository as chunk_store
from app.modules.rag.models import DocumentChunk
from app.modules.syllabus import mapping

log = logging.getLogger(__name__)


def _passages(n: int) -> str:
    return f"{n} passage" if n == 1 else f"{n} passages"


def embedding_text(title: str, chunk: chunking.Chunk) -> str:
    # Contextual header: a chunk from page 12 doesn't name its course or chapter; the title and path do.
    return f"{title}\n{chunk.heading_path}\n\n{chunk.text}".strip()


def run(db: Session, job_id: uuid.UUID, *, can_retry: bool) -> bool:
    """Process one ingestion job. Returns True if the caller should retry later (transient provider failure)."""
    job = job_repository.get(db, job_id)
    document = documents.get(db, job.document_id) if job and job.document_id else None
    if job is None or document is None:
        return False  # deleted while queued

    def fail(message: str) -> None:
        jobs.fail(db, job, message)
        document.status, document.error = "failed", message
        db.commit()

    return jobs.guarded(db, job, lambda: _ingest(db, job, document), fail, can_retry=can_retry)


def _ingest(db: Session, job: Job, document: Document) -> None:
    jobs.start(db, job, f"Processing {document.filename}")
    document.status, document.error = "processing", None
    db.commit()

    data = storage.get(document.storage_key)

    def on_pages(done: int, total: int) -> None:
        jobs.event(db, job, "extracting", f"Read {done} of {total} pages", 5 + 25 * done // total)
        db.commit()

    jobs.event(db, job, "extracting", "Reading the document", 5)
    db.commit()
    blocks, page_count = extraction.extract(document.file_type, data, on_pages)
    pieces = chunking.chunk_blocks(
        blocks, settings.chunk_max_tokens, settings.chunk_min_tokens, settings.chunk_overlap_tokens
    )
    if not pieces:
        raise extraction.ExtractionError("No text could be extracted from this file.")
    jobs.event(db, job, "chunking", f"Split into {_passages(len(pieces))}", 30)
    db.commit()

    embedder = providers.get_embedder()
    title = PurePath(document.filename).stem
    texts = [embedding_text(title, p) for p in pieces]
    hashes = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
    vectors = chunk_store.cached_embeddings(db, set(hashes), embedder.model)
    todo = [i for i, h in enumerate(hashes) if h not in vectors]
    reused = len(pieces) - len(todo)
    done = 0
    for batch_ids in token_batches([texts[i] for i in todo]):  # same batching as the provider: one request each
        batch = [todo[j] for j in batch_ids]
        batch_texts = [texts[i] for i in batch]
        for i, vector in zip(batch, embedder.embed(batch_texts, "document"), strict=True):
            vectors[hashes[i]] = vector
        usage.record(
            db,
            workspace_id=document.workspace_id,
            provider=embedder.provider,
            model=embedder.model,
            operation="embed_documents",
            input_tokens=sum(estimate_tokens(t) for t in batch_texts),
        )
        done += len(batch)
        jobs.event(db, job, "embedding", f"Embedded {done} of {len(todo)} passages", 30 + 65 * done // len(todo))
        db.commit()

    chunk_store.replace_chunks(
        db,
        document.id,
        [
            DocumentChunk(
                document_id=document.id,
                workspace_id=document.workspace_id,
                course_id=document.course_id,
                ordinal=n,
                heading_path=p.heading_path,
                page_start=p.page_start,
                page_end=p.page_end,
                content_type=p.content_type,
                content=p.text,
                content_hash=hashes[n],
                token_count=p.token_count,
                embedding=vectors[hashes[n]],
                embedding_model=embedder.model,
            )
            for n, p in enumerate(pieces)
        ],
    )
    document.status, document.page_count, document.chunk_count = "ready", page_count, len(pieces)
    document.processed_at = datetime.now(UTC)
    detail = f" ({reused} reused from cache)" if reused else ""
    jobs.succeed(db, job, f"Ready: {_passages(len(pieces))} indexed{detail}")
    db.commit()  # the document is searchable now; what follows may call the embedding API
    if document.course_id:
        mapping.remap_quietly(db, document.course_id)  # new passages → syllabus topics
    # PRD F7: lessons built on the old text, or on topics this document now covers, may be out of date.
    lessons.flag_document_changed(db, document.id, "A document this lesson cites was reprocessed.")
    lessons.flag_new_material(db, document.id)
    db.commit()
    assessments.extract_after_ingestion(db, document)  # question papers → draft questions (H3)
