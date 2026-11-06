import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.ai import providers
from app.config import settings
from app.core import mail, security
from app.database.session import get_db, get_session_factory
from app.main import app
from app.modules.documents import ingestion
from app.modules.documents import service as documents_service
from app.modules.lessons import service as lessons_service
from app.modules.research import service as research_service
from app.modules.syllabus import parsing
from app.modules.syllabus import service as syllabus_service
from app.orchestration import research_pipeline
from tests.samples import FakeChat, FakeEmbedder

TEST_DB = "semsaviour_test"
TEST_URL = settings.database_url.rsplit("/", 1)[0] + f"/{TEST_DB}"
PASSWORD = "correct horse battery"
security.N, security.P = 2**10, 1  # cheap hashes in tests; real parameters are checked in test_auth
settings.rate_limit_enabled = False  # test_auth turns it on for its own test


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    # Real Postgres + MinIO, real migrations (docs/decisions.md M13). Needs the compose services running.
    settings.s3_bucket = "semsaviour-test"
    with create_engine(settings.database_url, isolation_level="AUTOCOMMIT").connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB}):
            conn.execute(text(f"CREATE DATABASE {TEST_DB}"))

    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.attributes.update(database_url=TEST_URL, configure_logger=False)
    command.upgrade(cfg, "head")

    eng = create_engine(TEST_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    # One outer transaction per test, rolled back at the end; service commits become savepoints.
    # expire_on_commit=True: the session is shared across requests here, so it must not serve stale objects
    # (e.g. rows removed by ON DELETE CASCADE) that a per-request session would never see.
    with engine.connect() as conn:
        outer = conn.begin()
        session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=True)
        try:
            yield session
        finally:
            session.close()
            outer.rollback()


@pytest.fixture
def embedder(monkeypatch: pytest.MonkeyPatch) -> FakeEmbedder:
    fake = FakeEmbedder()
    monkeypatch.setattr(providers, "get_embedder", lambda: fake)
    return fake


@pytest.fixture
def chat(monkeypatch: pytest.MonkeyPatch) -> FakeChat:
    fake = FakeChat()
    monkeypatch.setattr(providers, "get_chat_model", lambda tier="fast": fake)
    return fake


@pytest.fixture
def lesson_queue(monkeypatch: pytest.MonkeyPatch) -> list[tuple[uuid.UUID, str | None]]:
    """Lessons queued for generation (recorded, not run: batches would otherwise generate for every confirm).
    Lesson tests drain it with tests.test_lessons.run_queued."""
    queue: list[tuple[uuid.UUID, str | None]] = []
    monkeypatch.setattr(lessons_service, "enqueue_generation", lambda lesson_id, request=None: queue.append((lesson_id, request)))
    return queue


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Emails the app sent (instead of SMTP)."""
    sent: list[dict[str, str]] = []
    monkeypatch.setattr(mail, "send", lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}) or True)
    return sent


def register(client: TestClient, email: str, name: str = "Student") -> dict[str, str]:
    """A new account; returns headers that act as it (Bearer token)."""
    r = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "display_name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.cookies['access_token']}"}


@pytest.fixture
def client(
    db: Session, embedder: FakeEmbedder, chat: FakeChat, lesson_queue: list, outbox: list, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """Signed in as alice@example.com, who owns every workspace the test creates through it."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_session_factory] = lambda: lambda: db
    # Background jobs run inline instead of through Redis/Celery: requests come back already processed.
    monkeypatch.setattr(documents_service, "enqueue_ingestion", lambda job_id: ingestion.run(db, job_id, can_retry=False))
    monkeypatch.setattr(syllabus_service, "enqueue_parse", lambda job_id: parsing.run(db, job_id, can_retry=False))
    monkeypatch.setattr(research_service, "enqueue_research", lambda rid: research_pipeline.run(db, rid, can_retry=False))
    try:
        test_client = TestClient(app, headers={"X-Requested-With": "test"})
        test_client.headers.update(register(test_client, "alice@example.com", "Alice"))
        test_client.cookies.clear()  # the header decides who's asking; tests switch users with their own headers
        yield test_client
    finally:
        app.dependency_overrides.clear()
