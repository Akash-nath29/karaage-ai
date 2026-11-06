"""Chunk → topic mapping (PRD C4 "map documents to topics", D5 chunk topic_id).

Each passage from a course's own materials is assigned to its most similar top-level topic when the cosine
similarity clears TOPIC_MATCH_THRESHOLD. Reuses the stored chunk vectors; only topic descriptions are embedded
(cached per topic until its text changes). Syllabus documents are excluded: they mention every topic.
"""

import hashlib
import logging
import uuid
from collections import defaultdict

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai import providers, usage
from app.ai.providers.base import ProviderError
from app.config import settings
from app.core.tokens import estimate_tokens
from app.modules.courses.models import Course
from app.modules.documents.models import Document
from app.modules.rag.models import DocumentChunk
from app.modules.syllabus import repository
from app.modules.syllabus.models import Topic

log = logging.getLogger(__name__)


def _normalized(rows: list[list[float]]) -> np.ndarray:
    matrix = np.asarray(rows, dtype=np.float32)
    return matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)


def topic_vectors(db: Session, course: Course) -> tuple[list[Topic], np.ndarray]:
    """Top-level topics and their normalized description vectors, embedded once and cached on the topic until its
    text changes. The caller commits."""
    units = {u.id: u for u in repository.units(db, course.id)}
    all_topics = repository.topics(db, course.id)
    top = [t for t in all_topics if t.parent_id is None]
    if not top:
        return [], np.zeros((0, 0), dtype=np.float32)
    subtopics: dict[uuid.UUID, list[str]] = defaultdict(list)
    for t in all_topics:
        if t.parent_id:
            subtopics[t.parent_id].append(t.title)
    embedder = providers.get_embedder()
    texts = [
        f"{course.title} > {units[t.unit_id].title} > {t.title}"
        + (f": {', '.join(subtopics[t.id])}" if subtopics[t.id] else "")
        for t in top
    ]
    hashes = [hashlib.sha256(f"{embedder.model}\n{text}".encode()).hexdigest() for text in texts]
    stale = [i for i, t in enumerate(top) if t.embedding is None or t.embedding_hash != hashes[i]]
    if stale:
        vectors = embedder.embed([texts[i] for i in stale], "query")
        for i, vector in zip(stale, vectors, strict=True):
            top[i].embedding, top[i].embedding_hash = vector, hashes[i]
        usage.record(
            db,
            workspace_id=course.workspace_id,
            provider=embedder.provider,
            model=embedder.model,
            operation="embed_topics",
            input_tokens=sum(estimate_tokens(texts[i]) for i in stale),
        )
    return top, _normalized([list(t.embedding) for t in top])  # type: ignore[arg-type]  # set above


def best_topics(topics: list[Topic], matrix: np.ndarray, vectors: list[list[float]]) -> list[Topic | None]:
    """The most similar topic for each vector, or None below TOPIC_MATCH_THRESHOLD."""
    if not topics or not vectors:
        return [None] * len(vectors)
    similarity = _normalized(vectors) @ matrix.T
    return [topics[b] if score >= settings.topic_match_threshold else None
            for b, score in zip(similarity.argmax(axis=1), similarity.max(axis=1), strict=True)]


def map_chunks(db: Session, course_id: uuid.UUID) -> int:
    """(Re)assign topics for every chunk in the course. Returns how many chunks got a topic. Caller commits."""
    course = db.get(Course, course_id)
    if course is None:
        return 0
    rows = db.execute(
        select(DocumentChunk.id, DocumentChunk.embedding, Document.kind)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.course_id == course_id)
    ).all()
    candidates = [r for r in rows if r.kind != "syllabus"]
    assignments: dict[uuid.UUID, uuid.UUID | None] = {r.id: None for r in rows}
    if candidates and repository.topics(db, course_id):
        top, matrix = topic_vectors(db, course)
        for row, topic in zip(candidates, best_topics(top, matrix, [list(r.embedding) for r in candidates]), strict=True):
            assignments[row.id] = topic.id if topic else None

    if assignments:
        db.execute(update(DocumentChunk), [{"id": cid, "topic_id": tid} for cid, tid in assignments.items()])
    return sum(1 for tid in assignments.values() if tid)


def remap_quietly(db: Session, course_id: uuid.UUID) -> None:
    """Mapping is best-effort: an unavailable embedding service must not fail a confirm or an ingestion.
    It reruns on the next structure change, ingestion or course reassignment."""
    try:
        map_chunks(db, course_id)
    except ProviderError as e:
        log.warning("topic mapping for course %s skipped: %s", course_id, e)
