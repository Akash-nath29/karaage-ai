import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Row, Text, cast, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import TSQUERY, distinct_on
from sqlalchemy.orm import Session

from app.modules.documents.models import Document
from app.modules.rag.models import DocumentChunk


def cached_embeddings(db: Session, hashes: set[str], model: str) -> dict[str, Any]:
    """Embedding cache (PRD §12.1): reuse vectors for identical embedded text and model, from any document."""
    if not hashes:
        return {}
    query = (
        select(DocumentChunk.content_hash, DocumentChunk.embedding)
        .where(DocumentChunk.content_hash.in_(hashes), DocumentChunk.embedding_model == model)
        .ext(distinct_on(DocumentChunk.content_hash))
    )
    return {h: v for h, v in db.execute(query)}


def replace_chunks(db: Session, document_id: uuid.UUID, chunks: list[DocumentChunk]) -> None:
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    db.add_all(chunks)


def set_course(db: Session, document_id: uuid.UUID, course_id: uuid.UUID | None) -> None:
    db.execute(
        update(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .values(course_id=course_id, topic_id=None)  # topics belong to a course; remapped by the caller
    )


def _scope(
    workspace_id: uuid.UUID, course_id: uuid.UUID | None, document_ids: list[uuid.UUID] | None = None
) -> list[ColumnElement[bool]]:
    # Never cross workspaces (PRD rule 14). A course sees its own materials plus workspace-wide ones (A8).
    conditions = [DocumentChunk.workspace_id == workspace_id]
    if document_ids:
        conditions.append(DocumentChunk.document_id.in_(document_ids))
    elif course_id:
        conditions.append(or_(DocumentChunk.course_id == course_id, DocumentChunk.course_id.is_(None)))
    return conditions


def vector_candidates(
    db: Session,
    workspace_id: uuid.UUID,
    course_id: uuid.UUID | None,
    query_vector: list[float],
    limit: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[uuid.UUID]:
    # Filtered HNSW can under-return; iterative scan keeps searching until `limit` rows pass the filter (R4).
    db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    rows = db.execute(
        select(DocumentChunk.id, distance)
        .where(*_scope(workspace_id, course_id, document_ids))
        .order_by(distance)
        .limit(limit)
    )
    return [chunk_id for chunk_id, _ in sorted(rows, key=lambda r: r[1])]  # relaxed_order may be slightly unsorted


def keyword_candidates(
    db: Session,
    workspace_id: uuid.UUID,
    course_id: uuid.UUID | None,
    query: str,
    limit: int,
    document_ids: list[uuid.UUID] | None = None,
) -> list[uuid.UUID]:
    # OR the query words: plainto_tsquery ANDs them, which misses on natural-language questions.
    tsquery = cast(func.replace(cast(func.plainto_tsquery("english", query), Text), "&", "|"), TSQUERY)
    rank = func.ts_rank_cd(DocumentChunk.tsv, tsquery)
    rows = db.scalars(
        select(DocumentChunk.id)
        .where(*_scope(workspace_id, course_id, document_ids), DocumentChunk.tsv.bool_op("@@")(tsquery))
        .order_by(rank.desc())
        .limit(limit)
    )
    return list(rows)


def fetch(db: Session, chunk_ids: list[uuid.UUID]) -> Sequence[Row[Any]]:
    """Chunk rows with their document's filename, in the order given. Skips the embedding column."""
    rows = db.execute(
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            Document.filename,
            DocumentChunk.page_start,
            DocumentChunk.page_end,
            DocumentChunk.heading_path,
            DocumentChunk.content,
            DocumentChunk.content_type,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.id.in_(chunk_ids))
    ).all()
    by_id = {row.id: row for row in rows}
    return [by_id[i] for i in chunk_ids if i in by_id]
