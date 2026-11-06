import json
import uuid
from typing import Any

import httpx
import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.usage import LlmUsage
from app.config import settings
from app.core import storage
from app.modules.documents import service as documents_service
from app.modules.rag.models import DocumentChunk
from tests.samples import LOREM, FakeEmbedder, make_blank_pdf, make_docx, make_pdf

SECTIONS = [
    ("Normalization", LOREM),
    ("Transactions", "A transaction is a unit of work with atomicity, consistency, isolation and durability. " * 4),
    ("Indexing", "B-tree indexes speed up range queries; hash indexes serve equality lookups. " * 4),
]


def workspace(client: TestClient, name: str = "WS") -> str:
    return client.post("/api/v1/workspaces", json={"name": name}).json()["id"]


def upload(client: TestClient, ws: str, data: bytes, name: str = "dbms.pdf", **form: str) -> httpx.Response:
    return client.post(f"/api/v1/workspaces/{ws}/documents", files={"file": (name, data)}, data=form)


def search(client: TestClient, ws: str, query: str, **body: Any) -> list[dict[str, Any]]:
    res = client.post(f"/api/v1/workspaces/{ws}/search", json={"query": query, **body})
    assert res.status_code == 200, res.text
    return res.json()


def sse_events(client: TestClient, job_id: str, last_event_id: int = 0) -> list[tuple[str, dict[str, Any], str]]:
    """(event name, data, id) for each SSE message until the stream ends."""
    events = []
    with client.stream("GET", f"/api/v1/jobs/{job_id}/events", headers={"Last-Event-ID": str(last_event_id)}) as res:
        assert res.headers["content-type"].startswith("text/event-stream")
        for message in res.read().decode().strip().split("\n\n"):
            fields = dict(line.split(": ", 1) for line in message.split("\n"))
            events.append((fields.get("event", "message"), json.loads(fields["data"]), fields.get("id", "")))
    return events


def test_upload_ingest_search_cite(client: TestClient, db: Session) -> None:
    ws = workspace(client)
    res = upload(client, ws, make_pdf(SECTIONS), kind="textbook")
    assert res.status_code == 201, res.text
    doc = res.json()
    assert (doc["status"], doc["file_type"], doc["kind"], doc["page_count"]) == ("ready", "pdf", "textbook", 3)
    assert doc["chunk_count"] >= 1

    hits = search(client, ws, "hash indexes for equality lookups")
    assert hits[0]["page_start"] <= 3 <= hits[0]["page_end"]  # cites the Indexing page
    assert hits[0]["filename"] == "dbms.pdf" and hits[0]["document_id"] == doc["id"]
    assert "Indexing" in hits[0]["heading_path"] or "Indexing" in hits[0]["content"]

    ops = set(db.scalars(select(LlmUsage.operation).where(LlmUsage.workspace_id == uuid.UUID(ws))))
    assert ops == {"embed_documents", "embed_query"}  # PRD §12 usage tracking


def test_job_events_stream_and_replay(client: TestClient) -> None:
    doc = upload(client, workspace(client), make_pdf(SECTIONS)).json()
    events = sse_events(client, doc["job_id"])
    stages = [data["stage"] for name, data, _ in events if name == "message"]
    assert stages[0] == "queued" and stages[-1] == "succeeded"
    assert {"started", "extracting", "chunking", "embedding"} <= set(stages)
    assert events[-1][0] == "end" and events[-1][1] == {"status": "succeeded"}
    assert [d["progress"] for n, d, _ in events if n == "message"][-1] == 100

    middle_id = int(events[2][2])  # reconnect with Last-Event-ID: only newer events replay
    replay = sse_events(client, doc["job_id"], last_event_id=middle_id)
    assert all(int(i) > middle_id for n, _, i in replay if n == "message")
    assert client.get(f"/api/v1/jobs/{uuid.uuid4()}/events").status_code == 404


def test_workspace_isolation_in_retrieval(client: TestClient) -> None:
    a, b = workspace(client, "A"), workspace(client, "B")
    upload(client, a, make_pdf(SECTIONS))
    assert search(client, a, "transaction isolation")  # found in A
    assert search(client, b, "transaction isolation") == []  # never crosses workspaces (PRD rule 14)


def test_course_scope_and_reassignment(client: TestClient, db: Session) -> None:
    ws = workspace(client)
    c1 = client.post(f"/api/v1/workspaces/{ws}/courses", json={"title": "DBMS"}).json()["id"]
    c2 = client.post(f"/api/v1/workspaces/{ws}/courses", json={"title": "OS"}).json()["id"]
    doc = upload(client, ws, make_pdf(SECTIONS), course_id=c1).json()
    assert doc["course_id"] == c1

    assert search(client, ws, "transaction", course_id=c1)
    assert search(client, ws, "transaction", course_id=c2) == []
    assert [d["id"] for d in client.get(f"/api/v1/workspaces/{ws}/documents", params={"course_id": c2}).json()] == []

    assert client.patch(f"/api/v1/documents/{doc['id']}", json={"course_id": c2}).json()["course_id"] == c2
    assert search(client, ws, "transaction", course_id=c2)  # chunks follow the document
    assert client.patch(f"/api/v1/documents/{doc['id']}", json={"course_id": None}).json()["course_id"] is None
    assert search(client, ws, "transaction", course_id=c1)  # unassigned = workspace-wide, visible to every course
    assert set(db.scalars(select(DocumentChunk.course_id).where(DocumentChunk.document_id == uuid.UUID(doc["id"])))) == {None}

    other = workspace(client, "other")
    other_course = client.post(f"/api/v1/workspaces/{other}/courses", json={"title": "X"}).json()["id"]
    assert client.patch(f"/api/v1/documents/{doc['id']}", json={"course_id": other_course}).status_code == 422


def test_upload_validation(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = workspace(client)
    pdf = make_pdf(SECTIONS)
    assert upload(client, ws, pdf).status_code == 201
    dup = upload(client, ws, pdf, name="copy.pdf")
    assert dup.status_code == 409 and "dbms.pdf" in dup.json()["detail"]
    assert upload(client, workspace(client, "other"), pdf).status_code == 201  # dedupe is per workspace
    assert upload(client, ws, b"MZ\x90\x00binary", name="evil.pdf").status_code == 415
    assert upload(client, ws, b"", name="empty.txt").status_code == 422
    assert upload(client, ws, make_docx(), kind="nonsense").status_code == 422
    assert upload(client, str(uuid.uuid4()), make_docx()).status_code == 404
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    assert upload(client, ws, make_docx(), name="big.docx").status_code == 413


def test_failed_extraction_is_reported(client: TestClient) -> None:
    doc = upload(client, workspace(client), make_blank_pdf(), name="scan.pdf").json()
    assert doc["status"] == "failed"
    assert doc["error"]  # "needs OCR" without Tesseract, "no text" with it
    assert client.get(f"/api/v1/jobs/{doc['job_id']}").json()["status"] == "failed"
    assert client.get(f"/api/v1/documents/{doc['id']}/status").json()["status"] == "failed"


def test_queue_unavailable_marks_failed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(job_id: uuid.UUID) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(documents_service, "enqueue_ingestion", broken)
    doc = upload(client, workspace(client), make_docx(), name="n.docx").json()
    assert doc["status"] == "failed" and "queue" in doc["error"]


def test_reprocess_reuses_embeddings(client: TestClient, embedder: FakeEmbedder) -> None:
    doc = upload(client, workspace(client), make_pdf(SECTIONS)).json()
    calls = embedder.calls
    again = client.post(f"/api/v1/documents/{doc['id']}/reprocess").json()
    assert again["status"] == "ready" and again["job_id"] != doc["job_id"]
    assert embedder.calls == calls  # every chunk came from the embedding cache
    last = sse_events(client, again["job_id"])[-2][1]
    assert "reused from cache" in last["message"]


def test_open_file_and_delete(client: TestClient) -> None:
    ws = workspace(client)
    pdf = make_pdf(SECTIONS)
    doc = upload(client, ws, pdf).json()

    res = client.get(f"/api/v1/documents/{doc['id']}/file", follow_redirects=False)
    assert res.status_code == 307
    signed = httpx.get(res.headers["location"])  # private bucket, reachable only via the signed URL
    assert signed.status_code == 200 and signed.content == pdf
    assert signed.headers["content-type"] == "application/pdf"
    assert "inline" in signed.headers["content-disposition"]
    key = f"documents/{doc['id']}"

    assert client.delete(f"/api/v1/documents/{doc['id']}").status_code == 204
    assert client.get(f"/api/v1/documents/{doc['id']}").status_code == 404
    assert search(client, ws, "transaction") == []  # removed from retrieval (PRD §10.5)
    with pytest.raises(ClientError):  # NoSuchKey
        storage.get(key)


def test_transient_provider_outage_retries_then_fails(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai import providers
    from app.ai.providers.base import TransientProviderError
    from app.modules.documents import ingestion

    monkeypatch.setattr(documents_service, "enqueue_ingestion", lambda job_id: None)  # drive the job by hand
    doc = upload(client, workspace(client), make_docx(), name="n.docx").json()

    class Down:
        provider, model = "fake", "down"

        def embed(self, texts: list[str], task: str) -> list[list[float]]:
            raise TransientProviderError("503 Service Unavailable")

    monkeypatch.setattr(providers, "get_embedder", lambda: Down())
    job_id = uuid.UUID(doc["job_id"])

    assert ingestion.run(db, job_id, can_retry=True) is True  # caller (Celery) schedules a retry
    assert client.get(f"/api/v1/documents/{doc['id']}").json()["status"] == "processing"

    assert ingestion.run(db, job_id, can_retry=False) is False  # retries exhausted
    after = client.get(f"/api/v1/documents/{doc['id']}").json()
    assert after["status"] == "failed" and "unavailable" in after["error"]
    job = client.get(f"/api/v1/jobs/{doc['job_id']}").json()
    assert job["attempts"] == 2 and job["status"] == "failed"
    stages = [d["stage"] for n, d, _ in sse_events(client, doc["job_id"]) if n == "message"]
    assert "retrying" in stages and stages[-1] == "failed"


def test_weighted_fusion() -> None:
    from app.modules.rag.service import fuse

    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    vector, keyword = [a, b], [c]

    def order(keyword_weight: float) -> list[uuid.UUID]:
        return [i for i, _ in fuse([vector, keyword], [1.0, keyword_weight])]

    assert order(1.0) == [a, c, b]  # keyword's top hit outranks vector's second
    assert order(0.3) == [a, b, c]  # down-weighted keyword: vector order first


def test_stalled_job_can_be_restarted(client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime, timedelta

    from app.modules.jobs.models import Job, JobEvent

    monkeypatch.setattr(documents_service, "enqueue_ingestion", lambda job_id: None)  # job never runs
    doc = upload(client, workspace(client), make_docx(), name="n.docx").json()
    assert doc["status"] == "queued"
    assert client.post(f"/api/v1/documents/{doc['id']}/reprocess").status_code == 409  # genuinely in progress

    old = datetime.now(UTC) - timedelta(minutes=16)  # worker died: no events since
    db.query(JobEvent).filter(JobEvent.job_id == uuid.UUID(doc["job_id"])).update({"created_at": old})
    db.query(Job).filter(Job.id == uuid.UUID(doc["job_id"])).update({"created_at": old})
    db.commit()
    again = client.post(f"/api/v1/documents/{doc['id']}/reprocess")
    assert again.status_code == 200 and again.json()["job_id"] != doc["job_id"]


def test_deleting_workspace_removes_stored_files(client: TestClient) -> None:
    ws = workspace(client)
    doc = upload(client, ws, make_docx(), name="n.docx").json()
    storage.get(f"documents/{doc['id']}")  # stored
    assert client.delete(f"/api/v1/workspaces/{ws}").status_code == 204
    with pytest.raises(ClientError):
        storage.get(f"documents/{doc['id']}")
