import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.prompts import tutor as prompts
from app.ai.providers.base import ProviderError
from app.ai.usage import LlmUsage
from app.config import settings
from app.modules.research import tavily
from app.modules.tutor import service
from app.modules.tutor.models import TutorMessage
from app.modules.tutor.schemas import MessageIn
from app.orchestration import tutor_pipeline
from tests.samples import FakeChat
from tests.test_documents import workspace
from tests.test_lessons import course_with_notes, no_web, reset  # noqa: F401  fixtures

ANSWER = "Atomicity means all or nothing [M1]. A made-up source [M7, M1]."


def ask(client: TestClient, sid: str, content: str, **body: Any) -> list[tuple[str, dict[str, Any]]]:
    res = client.post(f"/api/v1/tutor/sessions/{sid}/messages", json={"content": content, **body})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")
    events = []
    for message in res.text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in message.split("\n"))
        events.append((fields["event"], json.loads(fields["data"])))
    return events


@pytest.fixture
def ids(client: TestClient, course_with_notes: dict[str, str], lesson_queue: list) -> dict[str, str]:  # noqa: F811
    reset(client, course_with_notes, lesson_queue)
    return course_with_notes


def new_session(client: TestClient, ids: dict[str, str], **body: Any) -> dict[str, Any]:
    res = client.post("/api/v1/tutor/sessions", json={"workspace_id": ids["ws"], "topic_id": ids["topic"], **body})
    assert res.status_code == 201, res.text
    return res.json()


def test_sessions_context_and_crud(client: TestClient, ids: dict[str, str]) -> None:
    tutor = new_session(client, ids)
    assert (tutor["course_id"], tutor["topic_title"], tutor["mode"]) == (ids["course"], "ACID Properties", "doubt")
    assert tutor["course_title"]

    other = client.post(f"/api/v1/workspaces/{ids['ws']}/courses", json={"title": "Other"}).json()
    assert client.post("/api/v1/tutor/sessions", json={"workspace_id": ids["ws"], "topic_id": ids["topic"],
                                                       "course_id": other["id"]}).status_code == 422
    elsewhere = workspace(client, "Elsewhere")
    assert client.post("/api/v1/tutor/sessions", json={"workspace_id": elsewhere, "course_id": ids["course"]}).status_code == 422
    from_lesson_context = client.post("/api/v1/tutor/sessions", json={"course_id": ids["course"]}).json()
    assert from_lesson_context["workspace_id"] == ids["ws"]  # derived from the course
    assert client.post("/api/v1/tutor/sessions", json={}).status_code == 422
    client.delete(f"/api/v1/tutor/sessions/{from_lesson_context['id']}")
    general = client.post("/api/v1/tutor/sessions", json={"workspace_id": ids["ws"], "mode": "learn"}).json()
    assert general["course_id"] is None and general["mode"] == "learn"

    listed = client.get("/api/v1/tutor/sessions", params={"workspace_id": ids["ws"]}).json()
    assert {s["id"] for s in listed} == {tutor["id"], general["id"]}
    assert [s["id"] for s in client.get("/api/v1/tutor/sessions", params={"workspace_id": ids["ws"], "topic_id": ids["topic"]}).json()] == [tutor["id"]]
    assert client.get("/api/v1/tutor/sessions", params={"workspace_id": elsewhere}).json() == []

    assert client.delete(f"/api/v1/tutor/sessions/{tutor['id']}").status_code == 204
    assert client.get(f"/api/v1/tutor/sessions/{tutor['id']}").status_code == 404
    assert client.get(f"/api/v1/tutor/sessions/{tutor['id']}/messages").status_code == 404


def test_streamed_answer_with_citations_and_follow_ups(
    client: TestClient, chat: FakeChat, db: Session, ids: dict[str, str], no_web: None  # noqa: F811
) -> None:
    sid = new_session(client, ids)["id"]
    chat.stream_reply = f"{ANSWER}\n{prompts.FOLLOW_UPS}\n1. What is durability?\n- How does logging help?\n"
    events = ask(client, sid, "What is atomicity?")

    names = [name for name, _ in events]
    assert names[0] == "status" and names[-1] == "done" and "token" in names and "error" not in names
    streamed = "".join(data["text"] for name, data in events if name == "token")
    assert streamed.strip() == ANSWER  # the follow-up block never reaches the stream, even split across chunks
    answer = events[-1][1]["message"]
    assert answer["content"] == "Atomicity means all or nothing [M1]. A made-up source [M1]."  # unknown label dropped
    assert answer["suggestions"] == ["What is durability?", "How does logging help?"]
    assert (answer["status"], answer["model"], answer["mode"]) == ("complete", "fake-chat", "doubt")
    [citation] = answer["citations"]
    assert (citation["label"], citation["kind"], citation["filename"]) == ("M1", "material", "notes.pdf")
    assert "atomicity" in citation["quote"].lower() and citation["page_start"] == 1

    system, turns = chat.streams[-1]
    assert prompts.MODES["doubt"] in system and "untrusted" in system
    assert turns[-1][0] == "user" and "Current topic:" in turns[-1][1] and '<source id="M1"' in turns[-1][1]
    assert turns[-1][1].endswith("Student: What is atomicity?")

    history = client.get(f"/api/v1/tutor/sessions/{sid}/messages").json()
    assert [(m["role"], m["content"]) for m in history] == [("user", "What is atomicity?"), ("assistant", answer["content"])]
    assert client.get(f"/api/v1/tutor/sessions/{sid}").json()["title"] == "What is atomicity?"
    assert db.scalar(select(LlmUsage.operation).where(LlmUsage.operation == "tutor_answer"))

    # A follow-up in another mode sees the conversation so far and switches the session's mode
    chat.stream_reply = "What happens if the system crashes halfway through a transfer?"
    done = ask(client, sid, "And durability?", mode="socratic")[-1][1]["message"]
    system, turns = chat.streams[-1]
    assert prompts.MODES["socratic"] in system
    assert [role for role, _ in turns] == ["user", "assistant", "user"] and turns[0][1] == "What is atomicity?"
    assert done["mode"] == "socratic" and done["citations"] == [] and done["suggestions"] == []
    assert client.get(f"/api/v1/tutor/sessions/{sid}").json()["mode"] == "socratic"


def test_web_search_errors_budget_and_interruption(
    client: TestClient, chat: FakeChat, db: Session, ids: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = new_session(client, ids, mode="exam")["id"]
    page = "Atomicity guarantees that a transaction happens completely or not at all. Logs make undo possible. " * 5
    monkeypatch.setattr(tavily, "search", lambda query, n: [
        tavily.WebResult(url="http://127.0.0.1/admin", title="Internal", snippet="x", content=page, score=0.99, published_date=None),
        tavily.WebResult(url="https://en.wikipedia.org/wiki/ACID?utm_source=x", title="ACID", snippet="ACID", content=page,
                         score=0.9, published_date=None),
    ])
    chat.stream_reply = "Answer for 5 marks [W1]."
    answer = ask(client, sid, "Explain atomicity for 5 marks", web=True)[-1][1]["message"]
    [web] = answer["citations"]
    assert (web["kind"], web["url"], web["domain"]) == ("web", "https://en.wikipedia.org/wiki/ACID", "en.wikipedia.org")
    assert "127.0.0.1" not in chat.streams[-1][1][-1][1]  # unsafe URL never reaches the model
    assert prompts.MODES["exam"] in chat.streams[-1][0]
    assert db.scalar(select(LlmUsage.id).where(LlmUsage.operation == "web_search"))

    # A provider failure mid-stream: error event, partial answer kept and marked
    chat.stream_reply, chat.stream_error = "Isolation keeps concurrent transactions apart.", ProviderError("overloaded")
    events = ask(client, sid, "Explain isolation")
    assert [name for name, _ in events][-2:] == ["error", "done"] and "overloaded" in events[-2][1]["detail"]
    failed = events[-1][1]["message"]
    assert failed["status"] == "error" and failed["content"] == "Isolati"
    chat.stream_error = None

    # The client disconnects mid-answer: what was generated is saved as interrupted
    chat.stream_reply = "Consistency means every transaction moves the database between valid states. " * 3
    question = service.add_question(db, uuid.UUID(sid), MessageIn(content="Consistency?"))
    stream = tutor_pipeline.answer(lambda: db, question.id, False)
    while not next(stream).startswith("event: token"):
        pass
    stream.close()
    saved = db.scalars(select(TutorMessage).where(TutorMessage.session_id == uuid.UUID(sid))
                       .order_by(TutorMessage.created_at.desc())).first()
    assert saved is not None and saved.status == "interrupted" and chat.stream_reply.startswith(saved.content) and saved.content

    # Over budget: a plain 429 before any stream opens, nothing saved
    before = len(client.get(f"/api/v1/tutor/sessions/{sid}/messages").json())
    monkeypatch.setattr(settings, "workspace_monthly_tokens", 1)
    res = client.post(f"/api/v1/tutor/sessions/{sid}/messages", json={"content": "More?"})
    assert res.status_code == 429 and "budget" in res.json()["detail"]
    assert len(client.get(f"/api/v1/tutor/sessions/{sid}/messages").json()) == before
