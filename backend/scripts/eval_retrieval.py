"""Retrieval benchmark (PRD §16): Hit@1, Recall@5/10 and MRR@10 on real course material, real embedding provider.

Run from backend/ with the compose services up:
    python -m scripts.eval_retrieval              # ingest once (cached), then score
    python -m scripts.eval_retrieval --reingest   # after changing chunking settings (CHUNK_* env vars)

Uses the dev database: documents land in a workspace called "Retrieval benchmark".
"""

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path
from statistics import mean

from sqlalchemy.orm import Session

from app.ai import providers, usage
from app.config import settings
from app.core.tokens import estimate_tokens
from app.database.session import SessionLocal
from app.modules.documents import ingestion
from app.modules.documents import repository as document_repository
from app.modules.documents import service as documents
from app.modules.rag import repository as chunks
from app.modules.rag.service import fuse
from app.modules.workspaces import service as workspaces
from app.modules.workspaces.schemas import WorkspaceCreate

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = Path(__file__).resolve().parents[1] / "tests" / "benchmark" / "aiml_r23.json"
WORKSPACE = "Retrieval benchmark"
K = 10


def ensure_ingested(db: Session, path: Path, kind: str, reingest: bool) -> uuid.UUID:
    workspace = next((w for w in workspaces.list_all(db) if w.name == WORKSPACE), None) or workspaces.create(
        db, WorkspaceCreate(name=WORKSPACE, description="Created by scripts/eval_retrieval.py")
    )
    data = path.read_bytes()
    documents.enqueue_ingestion = lambda job_id: ingestion.run(db, job_id, can_retry=False)  # inline, no worker
    doc = document_repository.find_by_checksum(db, workspace.id, hashlib.sha256(data).hexdigest())
    if doc is None or reingest or doc.status != "ready":
        print(f"Ingesting {path.name} with {settings.embedding_provider}/{settings.embedding_model} …", flush=True)
        doc = documents.upload(db, workspace.id, path.name, data, kind, None) if doc is None else documents.reprocess(db, doc.id)
    if doc.status != "ready":
        sys.exit(f"Ingestion failed: {doc.error}")
    print(f"{doc.filename}: {doc.page_count} pages, {doc.chunk_count} chunks "
          f"(max {settings.chunk_max_tokens}, min {settings.chunk_min_tokens}, overlap {settings.chunk_overlap_tokens})")
    return workspace.id


def first_relevant_rank(db: Session, ranking: list[uuid.UUID], expected: set[int]) -> int | None:
    for rank, row in enumerate(chunks.fetch(db, ranking[:K]), start=1):
        if row.page_start is not None and any(row.page_start <= p <= row.page_end for p in expected):
            return rank
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reingest", action="store_true", help="re-chunk and re-embed (cache reuses unchanged chunks)")
    args = parser.parse_args()
    bench = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    queries = bench["queries"]

    with SessionLocal() as db:
        ws = ensure_ingested(db, ROOT / bench["document"], bench["kind"], args.reingest)
        embedder = providers.get_embedder()
        vectors = embedder.embed([q["q"] for q in queries], "query")  # one batched call
        usage.record(db, workspace_id=ws, provider=embedder.provider, model=embedder.model, operation="embed_query",
                     input_tokens=sum(estimate_tokens(q["q"]) for q in queries))
        db.commit()

        n = settings.retrieval_candidates
        ranks: dict[str, list[int | None]] = {"vector": [], "keyword": [], "hybrid": []}
        for q, vector in zip(queries, vectors, strict=True):
            by_vector = chunks.vector_candidates(db, ws, None, vector, n)
            by_keyword = chunks.keyword_candidates(db, ws, None, q["q"], n)
            hybrid = [chunk_id for chunk_id, _ in fuse([by_vector, by_keyword], [1.0, settings.retrieval_keyword_weight])]
            for mode, ranking in (("vector", by_vector), ("keyword", by_keyword), ("hybrid", hybrid)):
                ranks[mode].append(first_relevant_rank(db, ranking, set(q["pages"])))
            db.rollback()  # end the read transaction (SET LOCAL in vector search)

    print(f"\n{len(queries)} queries · relevant = passage page range overlaps an expected page"
          f" · hybrid keyword weight {settings.retrieval_keyword_weight}\n")
    print(f"{'mode':8} {'Hit@1':>6} {'Recall@5':>9} {'Recall@10':>10} {'MRR@10':>7}")
    for mode, rs in ranks.items():
        hit = lambda k, rs=rs: mean(1 if r is not None and r <= k else 0 for r in rs)  # noqa: E731
        mrr = mean(1 / r if r else 0 for r in rs)
        print(f"{mode:8} {hit(1):6.2f} {hit(5):9.2f} {hit(K):10.2f} {mrr:7.3f}")

    misses = [(q["q"], q["pages"], r) for q, r in zip(queries, ranks["hybrid"], strict=True) if r is None or r > 3]
    if misses:
        print("\nHybrid: relevant passage missing from top 3")
        for question, pages, rank in misses:
            print(f"  rank {rank or '>10':>4}  pages {pages}  {question}")


if __name__ == "__main__":
    main()
