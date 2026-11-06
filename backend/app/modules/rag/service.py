"""Hybrid retrieval (PRD D6): vector + keyword candidates → weighted reciprocal-rank fusion → dedupe → top k.

No cross-encoder rerank step: on the benchmark it lowered Hit@1 and cost ~3.6 s/query on CPU (docs/decisions.md D9).
"""

import hashlib
import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from app.ai import providers, usage
from app.config import settings
from app.core.tokens import estimate_tokens
from app.modules.rag import repository
from app.modules.rag.schemas import Passage, SearchRequest
from app.modules.workspaces import service as workspaces

RRF_K = 60  # standard reciprocal-rank-fusion constant


def fuse(rankings: list[list[uuid.UUID]], weights: list[float]) -> list[tuple[uuid.UUID, float]]:
    scores: dict[uuid.UUID, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights, strict=True):
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] += weight / (RRF_K + rank + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def search(db: Session, workspace_id: uuid.UUID, request: SearchRequest) -> list[Passage]:
    workspaces.get(db, workspace_id)
    embedder = providers.get_embedder()
    query_vector = embedder.embed([request.query], "query")[0]
    usage.record(
        db,
        workspace_id=workspace_id,
        provider=embedder.provider,
        model=embedder.model,
        operation="embed_query",
        input_tokens=estimate_tokens(request.query),
    )

    n = settings.retrieval_candidates
    fused = fuse(
        [
            repository.vector_candidates(db, workspace_id, request.course_id, query_vector, n, request.document_ids),
            repository.keyword_candidates(db, workspace_id, request.course_id, request.query, n, request.document_ids),
        ],
        [1.0, settings.retrieval_keyword_weight],
    )[:n]
    scores = dict(fused)
    passages, seen = [], set()
    for row in repository.fetch(db, [chunk_id for chunk_id, _ in fused]):
        digest = hashlib.sha256(row.content.encode()).digest()
        if digest in seen:  # same text in two files (e.g. a re-uploaded copy under another name)
            continue
        seen.add(digest)
        passages.append(Passage(chunk_id=row.id, score=round(scores[row.id], 5), **row._asdict()))
    db.commit()  # usage row
    return passages[: request.top_k or settings.retrieval_top_k]
