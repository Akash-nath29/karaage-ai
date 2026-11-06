"""Who can do what (PRD §4, A11–A13), tenant isolation (Workflows 1 and 7), row-level security (D27), lesson
visibility (D28), learning analytics and usage (Module I, D30–D32)."""

import re
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import row_security
from app.main import app
from tests.conftest import register
from tests.samples import FakeChat
from tests.test_assessments import GENERATED, bank, ids  # noqa: F401  fixture
from tests.test_documents import upload, workspace
from tests.test_lessons import course_with_notes, lesson_reply, run_queued  # noqa: F401  fixture

ALICE: dict[str, str] = {}  # the default client's own header
PUBLIC = {("GET", "/api/v1/health"), ("GET", "/api/v1/invitations/{token}")} | {
    ("POST", f"/api/v1/auth/{p}") for p in ("register", "login", "refresh", "logout", "verify-email", "forgot-password",
                                           "reset-password")}


def call(client: TestClient, method: str, path: str, who: dict[str, str] | None = None, status: int = 200, **kwargs: Any) -> Any:
    res = client.request(method, f"/api/v1{path}", headers=who or ALICE, **kwargs)
    assert res.status_code == status, f"{method} {path}: {res.status_code} {res.text}"
    return res.json() if res.content else None


def join(client: TestClient, ws: str, who: dict[str, str], role: str = "viewer") -> None:
    link = call(client, "POST", f"/workspaces/{ws}/invitations", status=201, json={"role": role})
    assert call(client, "POST", f"/invitations/{link['url'].rsplit('/', 1)[1]}/accept", who)["role"] == role


def user_id(client: TestClient, who: dict[str, str] | None = None) -> str:
    return call(client, "GET", "/users/me", who)["id"]


def test_every_route_needs_sign_in(client: TestClient) -> None:
    anonymous = TestClient(app, headers={"X-Requested-With": "test"})
    checked = 0
    for route, methods in app.openapi()["paths"].items():  # every route, however routers are nested
        for method in (m.upper() for m in methods):
            if (method, route) in PUBLIC:
                continue
            path = re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), route)
            assert anonymous.request(method, path).status_code == 401, f"{method} {route} is open"
            checked += 1
    assert checked > 70


def test_workflow_7_tenant_isolation(client: TestClient, ids: dict[str, Any]) -> None:  # noqa: F811
    ws, course, topic, doc = ids["ws"], ids["course"], ids["topic"], ids["doc"]
    # 1. User A has a private workspace, with personal data in it.
    talk = call(client, "POST", "/tutor/sessions", status=201, json={"topic_id": topic})
    call(client, "PUT", f"/topics/{topic}/progress", json={"studied": True})
    private = call(client, "POST", f"/topics/{topic}/lessons/generate", status=202, json={"depth": "beginner", "visibility": "private"})
    bob = register(client, "bob@example.com", "Bob")

    # 2–3. User B is denied everything in it: to them it doesn't exist.
    for path in [f"/workspaces/{ws}", f"/workspaces/{ws}/courses", f"/workspaces/{ws}/documents", f"/workspaces/{ws}/members",
                 f"/courses/{course}", f"/courses/{course}/units", f"/topics/{topic}", f"/documents/{doc}", f"/documents/{doc}/file",
                 f"/courses/{course}/progress", f"/courses/{course}/questions", f"/tutor/sessions/{talk['id']}",
                 f"/tutor/sessions?workspace_id={ws}", f"/lessons/{private['id']}", f"/jobs/{private['job_id']}",
                 f"/workspaces/{ws}/lessons", f"/workspaces/{ws}/usage"]:
        call(client, "GET", path, bob, 404)
    call(client, "POST", f"/workspaces/{ws}/courses", bob, 404, json={"title": "Mine now"})
    call(client, "POST", f"/workspaces/{ws}/search", bob, 404, json={"query": "atomicity"})
    call(client, "POST", "/tutor/sessions", bob, 404, json={"course_id": course})
    call(client, "DELETE", f"/workspaces/{ws}", bob, 404)
    assert call(client, "GET", "/workspaces", bob) == []

    # 4. User A invites user B (the link's preview is public).
    link = call(client, "POST", f"/workspaces/{ws}/invitations", status=201, json={"role": "viewer"})
    token = link["url"].rsplit("/", 1)[1]
    preview = TestClient(app).get(f"/api/v1/invitations/{token}").json()
    assert (preview["role"], preview["invited_by"]) == ("viewer", "Alice")
    assert call(client, "POST", f"/invitations/{token}/accept", bob)["role"] == "viewer"

    # 5. B gets exactly the viewer role: shared content yes, managing it no.
    for path in [f"/courses/{course}", f"/topics/{topic}", f"/documents/{doc}", f"/workspaces/{ws}/documents",
                 f"/workspaces/{ws}/members"]:
        call(client, "GET", path, bob)
    call(client, "GET", f"/courses/{course}/questions", bob, 403)  # answer keys: editors only (D32)
    assert call(client, "POST", f"/workspaces/{ws}/search", bob, json={"query": "atomicity"})  # retrieval works
    call(client, "POST", f"/workspaces/{ws}/courses", bob, 403, json={"title": "x"})
    call(client, "PATCH", f"/courses/{course}", bob, 403, json={"title": "x"})
    call(client, "POST", f"/courses/{course}/syllabus/confirm", bob, 403)
    call(client, "POST", f"/workspaces/{ws}/documents", bob, 403, files={"file": ("n.txt", b"notes", "text/plain")})
    call(client, "DELETE", f"/documents/{doc}", bob, 403)
    call(client, "POST", f"/courses/{course}/questions", bob, 403, json={"text": "Q?", "type": "short", "marks": 2})
    call(client, "POST", f"/workspaces/{ws}/invitations", bob, 403, json={"role": "viewer"})
    call(client, "GET", f"/workspaces/{ws}/audit", bob, 403)
    call(client, "DELETE", f"/workspaces/{ws}", bob, 403)

    # 6. B still can't see A's conversations, private lessons or progress, and A can't see B's.
    call(client, "GET", f"/tutor/sessions/{talk['id']}", bob, 404)
    call(client, "GET", f"/tutor/sessions/{talk['id']}/messages", bob, 404)
    call(client, "POST", f"/tutor/sessions/{talk['id']}/messages", bob, 404, json={"content": "hi"})
    assert call(client, "GET", f"/tutor/sessions?workspace_id={ws}", bob) == []
    call(client, "GET", f"/lessons/{private['id']}", bob, 404)
    assert private["id"] not in {l["id"] for l in call(client, "GET", f"/topics/{topic}/lessons", bob)}
    assert call(client, "GET", f"/courses/{course}/progress", bob)["studied"] == 0
    assert call(client, "GET", f"/courses/{course}/progress")["studied"] == 1
    bobs = call(client, "POST", "/tutor/sessions", bob, 201, json={"topic_id": topic})
    call(client, "GET", f"/tutor/sessions/{bobs['id']}", status=404)
    assert [s["id"] for s in call(client, "GET", f"/tutor/sessions?workspace_id={ws}")] == [talk["id"]]


def test_roles_members_and_invitations(client: TestClient, outbox: list[dict[str, str]]) -> None:
    """A11 matrix, A12 invitations, A13 removed members."""
    ws = workspace(client, "Study group")
    course = call(client, "POST", f"/workspaces/{ws}/courses", status=201, json={"title": "OS"})["id"]
    bob, carol = register(client, "bob@example.com", "Bob"), register(client, "carol@example.com", "Carol")
    join(client, ws, bob, "editor")
    join(client, ws, carol, "admin")
    alice_id, bob_id, carol_id = user_id(client), user_id(client, bob), user_id(client, carol)

    # Editors upload, and change or delete only their own documents.
    mine = upload(client, ws, b"Bob's notes on paging.", name="bob.txt", kind="notes")
    assert mine.status_code == 201  # as Alice: the default header
    bobs = client.post(f"/api/v1/workspaces/{ws}/documents", headers=bob, files={"file": ("b.txt", b"Bob on TLBs.", "text/plain")})
    assert bobs.status_code == 201
    call(client, "DELETE", f"/documents/{mine.json()['id']}", bob, 403)
    call(client, "PATCH", f"/documents/{mine.json()['id']}", bob, 403, json={"kind": "textbook"})
    call(client, "DELETE", f"/documents/{bobs.json()['id']}", bob, 204)
    call(client, "PATCH", f"/courses/{course}", bob, 403, json={"title": "x"})  # courses are admin work
    call(client, "PATCH", f"/courses/{course}", carol, json={"title": "Operating Systems"})

    # Admins manage editors and viewers; only the owner manages admins; nobody changes the owner.
    call(client, "PATCH", f"/workspaces/{ws}/members/{bob_id}", carol, json={"role": "viewer"})
    call(client, "PATCH", f"/workspaces/{ws}/members/{bob_id}", carol, 403, json={"role": "admin"})
    call(client, "PATCH", f"/workspaces/{ws}/members/{carol_id}", carol, 403, json={"role": "editor"})
    call(client, "PATCH", f"/workspaces/{ws}/members/{alice_id}", carol, 403, json={"role": "viewer"})
    call(client, "PATCH", f"/workspaces/{ws}/members/{alice_id}", status=403, json={"role": "admin"})
    call(client, "PATCH", f"/workspaces/{ws}/members/{bob_id}", status=422, json={"role": "owner"})
    call(client, "POST", f"/workspaces/{ws}/invitations", carol, 403, json={"role": "admin"})
    call(client, "DELETE", f"/workspaces/{ws}/members/{alice_id}", carol, 403)
    call(client, "DELETE", f"/workspaces/{ws}/members/{alice_id}", status=409)  # the owner can't leave
    call(client, "DELETE", f"/workspaces/{ws}", carol, 403)
    assert [m["role"] for m in call(client, "GET", f"/workspaces/{ws}/members", bob)] == ["owner", "admin", "viewer"]

    # A13: a removed member loses access; their private data comes back when they rejoin.
    talk = call(client, "POST", "/tutor/sessions", bob, 201, json={"course_id": course})
    call(client, "DELETE", f"/workspaces/{ws}/members/{bob_id}", carol, 204)
    call(client, "GET", f"/courses/{course}", bob, 404)
    call(client, "GET", f"/tutor/sessions/{talk['id']}", bob, 404)
    join(client, ws, bob)
    call(client, "GET", f"/tutor/sessions/{talk['id']}", bob)
    call(client, "DELETE", f"/workspaces/{ws}/members/{bob_id}", bob, 204)  # leaving
    call(client, "GET", f"/courses/{course}", bob, 404)

    # Email invitations: sent, single use, only for that address, which must be confirmed.
    sent = call(client, "POST", f"/workspaces/{ws}/invitations", status=201, json={"email": "Dave@Example.com", "role": "editor"})
    assert sent["emailed"] and sent["email"] == "dave@example.com" and outbox[-1]["to"] == "dave@example.com"
    token = re.search(r"/invite/([\w-]+)", outbox[-1]["body"]).group(1)  # type: ignore[union-attr]
    call(client, "POST", f"/invitations/{token}/accept", bob, 403)  # someone else's invitation
    dave = register(client, "dave@example.com", "Dave")
    assert "confirm" in call(client, "POST", f"/invitations/{token}/accept", dave, 403)["detail"].lower()
    verify = re.search(r"token=([\w-]+)", outbox[-1]["body"]).group(1)  # type: ignore[union-attr]
    call(client, "POST", "/auth/verify-email", status=204, json={"token": verify})
    assert call(client, "POST", f"/invitations/{token}/accept", dave)["role"] == "editor"
    call(client, "POST", f"/invitations/{token}/accept", bob, 410)  # used up
    call(client, "POST", f"/workspaces/{ws}/invitations", status=409, json={"email": "dave@example.com"})  # already in

    # Revoked and expired links stop working.
    link = call(client, "POST", f"/workspaces/{ws}/invitations", status=201, json={"role": "viewer", "max_uses": 5})
    active = call(client, "GET", f"/workspaces/{ws}/invitations")
    assert link["id"] in {i["id"] for i in active} and sent["id"] not in {i["id"] for i in active}  # Dave's is used up
    call(client, "DELETE", f"/workspaces/{ws}/invitations/{link['id']}", carol, 204)
    call(client, "POST", f"/invitations/{link['url'].rsplit('/', 1)[1]}/accept", bob, 410)
    call(client, "GET", f"/invitations/{link['url'].rsplit('/', 1)[1]}", status=410)
    call(client, "GET", "/invitations/not-a-real-token", status=404)

    actions = {a["action"] for a in call(client, "GET", f"/workspaces/{ws}/audit")}
    assert {"workspace.created", "member.joined", "member.role_changed", "member.removed", "member.left",
            "invitation.created", "invitation.revoked", "document.deleted"} <= actions
    call(client, "GET", f"/workspaces/{ws}/audit", dave, 403)


def test_row_level_security(client: TestClient, db: Session) -> None:
    """D27: even a query that forgets its WHERE clause only sees the requesting user's rows."""
    ws = workspace(client)
    call(client, "POST", f"/workspaces/{ws}/courses", status=201, json={"title": "DBMS"})
    call(client, "POST", "/tutor/sessions", status=201, json={"workspace_id": ws})
    bob = register(client, "bob@example.com", "Bob")
    alice_id, bob_id = user_id(client), user_id(client, bob)

    def count(as_user: str, table: str) -> int:
        savepoint = db.begin_nested()
        row_security(db.connection(), as_user)
        found = db.scalar(text(f"SELECT count(*) FROM {table} WHERE workspace_id = :w"), {"w": uuid.UUID(ws)})
        savepoint.rollback()
        return found  # type: ignore[return-value]

    assert (count(alice_id, "courses"), count(alice_id, "tutor_sessions")) == (1, 1)
    assert (count(bob_id, "courses"), count(bob_id, "tutor_sessions")) == (0, 0)  # not a member
    join(client, ws, bob)
    assert (count(bob_id, "courses"), count(bob_id, "tutor_sessions")) == (1, 0)  # member, but not his conversation

    savepoint = db.begin_nested()
    row_security(db.connection(), bob_id)
    with pytest.raises(DBAPIError, match="row-level security"):
        db.execute(text("INSERT INTO tutor_sessions (id, workspace_id, user_id, mode, title) "
                        "VALUES (gen_random_uuid(), :w, :u, 'doubt', 'planted')"), {"w": uuid.UUID(ws), "u": uuid.UUID(alice_id)})
    savepoint.rollback()


def test_lesson_visibility(client: TestClient, chat: FakeChat, db: Session, lesson_queue: list,
                           ids: dict[str, Any]) -> None:  # noqa: F811
    """D28: viewers' lessons stay private; editors share, and publish their private ones."""
    ws, topic = ids["ws"], ids["topic"]
    chat.replies["LlmLesson"] = lesson_reply()
    bob = register(client, "bob@example.com", "Bob")
    join(client, ws, bob)
    shared = next(l for l in call(client, "GET", f"/topics/{topic}/lessons") if l["visibility"] == "workspace")  # the batch's

    call(client, "POST", f"/topics/{topic}/lessons/generate", bob, 403, json={"visibility": "workspace"})
    bobs = call(client, "POST", f"/topics/{topic}/lessons/generate", bob, 202, json={"depth": "detailed"})
    assert (bobs["visibility"], bobs["owner_id"]) == ("private", user_id(client, bob))
    run_queued(db, lesson_queue)
    assert call(client, "GET", f"/lessons/{bobs['id']}", bob)["lesson"]["current_version"] == 1
    call(client, "GET", f"/lessons/{bobs['id']}", status=404)  # not even the owner of the workspace
    assert bobs["id"] not in {l["id"] for l in call(client, "GET", f"/topics/{topic}/lessons")}
    call(client, "POST", f"/lessons/{shared['id']}/regenerate", bob, 403)
    call(client, "POST", f"/lessons/{shared['id']}/enrich", bob, 403, json={"request": "more examples"})
    call(client, "POST", f"/lessons/{bobs['id']}/publish", bob, 403)  # publishing is Editor+

    call(client, "PATCH", f"/workspaces/{ws}/members/{user_id(client, bob)}", json={"role": "editor"})
    call(client, "POST", f"/lessons/{bobs['id']}/publish", bob, 409)  # a shared detailed lesson exists already
    alices = call(client, "POST", f"/topics/{topic}/lessons/generate", status=202, json={"depth": "beginner", "visibility": "private"})
    call(client, "POST", f"/lessons/{alices['id']}/publish", status=409)  # nothing generated yet
    run_queued(db, lesson_queue)
    assert call(client, "POST", f"/lessons/{alices['id']}/publish")["visibility"] == "workspace"
    assert alices["id"] in {l["id"] for l in call(client, "GET", f"/topics/{topic}/lessons", bob)}
    listed = call(client, "GET", f"/workspaces/{ws}/lessons", bob)
    assert {l["id"] for l in listed} == {alices["id"], bobs["id"]}  # readable ones: shared + his own
    assert {l["id"] for l in call(client, "GET", f"/workspaces/{ws}/lessons")} == {alices["id"]}
    assert listed[0]["topic_title"] == "ACID Properties" and listed[0]["course_title"]


def test_learning_analytics_and_usage(client: TestClient, chat: FakeChat, ids: dict[str, Any],  # noqa: F811
                                      monkeypatch: pytest.MonkeyPatch) -> None:
    ws, course, topic = ids["ws"], ids["course"], ids["topic"]
    bob = register(client, "bob@example.com", "Bob")
    join(client, ws, bob)
    bank(client, ids)
    call(client, "PUT", f"/topics/{topic}/progress", json={"studied": True})
    talk = call(client, "POST", "/tutor/sessions", status=201, json={"topic_id": topic})
    quiz = call(client, "POST", f"/topics/{topic}/quizzes", status=202, json={"count": 3, "types": ["mcq", "numerical", "fill_blank"]})
    keys = {"mcq": "0", "numerical": "4", "fill_blank": "atomicity"}
    call(client, "POST", f"/quizzes/{quiz['id']}/attempts", status=201, json={"answers": [
        {"question_id": q["id"], "answer": keys[q["type"]]} for q in quiz["questions"]]})

    stats = call(client, "GET", "/users/me/learning-analytics")
    assert (stats["courses_enrolled"], stats["topics_completed"], stats["topics_remaining"]) == (1, 1, 2)
    assert (stats["quiz_attempts"], stats["average_accuracy"]) == (1, 1.0)
    assert stats["recent_sessions"][0]["session_id"] == talk["id"] and stats["courses"][0]["completed"] == 1
    assert stats["weak_topics"] == [] and stats["revision_due"] == []
    theirs = call(client, "GET", "/users/me/learning-analytics", bob)  # per user (§I)
    assert (theirs["courses_enrolled"], theirs["topics_completed"], theirs["quiz_attempts"], theirs["recent_sessions"]) == (1, 0, 0, [])
    call(client, "GET", f"/quizzes/{quiz['id']}", bob, 404)
    assert call(client, "GET", f"/courses/{course}/quizzes", bob) == []

    # D32: new questions from a viewer's quiz wait in the bank as drafts.
    chat.replies["LlmQuizWork"] = GENERATED
    call(client, "POST", f"/topics/{topic}/quizzes", bob, 202, json={"count": 1, "types": ["long"]})
    drafts = call(client, "GET", f"/courses/{course}/questions?status=draft")
    assert [q["text"] for q in drafts] == ["Explain durability and how logging provides it."]

    usage = call(client, "GET", f"/workspaces/{ws}/usage")
    assert usage["tokens"] > 0 and usage["token_budget"] == settings.workspace_monthly_tokens
    people = {m["name"]: m["tokens"] for m in usage["by_member"]}
    assert people["Alice"] > 0 and people["Bob"] == 120  # Bob's quiz: one fake call (100 in + 20 out)
    assert call(client, "GET", f"/workspaces/{ws}/usage", bob)["by_member"] is None  # admins only
    mine = call(client, "GET", "/users/me/usage")
    assert mine["tokens"] == people["Alice"] and mine["by_workspace"][0]["workspace_id"] == ws

    monkeypatch.setattr(settings, "user_monthly_tokens", 100)  # Bob has used 120 (§12.6 per-user limit)
    bobs = call(client, "POST", "/tutor/sessions", bob, 201, json={"topic_id": topic})
    assert "monthly AI allowance" in call(client, "POST", f"/tutor/sessions/{bobs['id']}/messages", bob, 429,
                                          json={"content": "Explain atomicity"})["detail"]
