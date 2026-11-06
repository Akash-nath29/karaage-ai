"""Accounts and sessions (PRD A1–A3, docs/decisions.md D25–D26, D29)."""

import re
import uuid
from datetime import timedelta

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.core import security
from app.main import app
from app.modules.tutor.models import TutorSession
from app.modules.users import service
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember
from scripts.claim_data import LEGACY, claim
from tests.conftest import PASSWORD, register
from tests.samples import make_png


@pytest.fixture
def browser(client: TestClient) -> TestClient:
    """A second client that keeps cookies like a browser (no Authorization header). `client` sets up the app."""
    return TestClient(app, headers={"X-Requested-With": "test"})


def link_token(mail: dict[str, str]) -> str:
    return re.search(r"token=([\w-]+)", mail["body"]).group(1)  # type: ignore[union-attr]


def test_register_login_refresh_logout(browser: TestClient, outbox: list[dict[str, str]],
                                       monkeypatch: pytest.MonkeyPatch) -> None:
    r = browser.post("/api/v1/auth/register", json={"email": " Ravi@Example.com ", "password": PASSWORD, "display_name": "Ravi"})
    assert r.status_code == 201 and r.json()["email"] == "ravi@example.com" and r.json()["email_verified"] is False
    assert {"access_token", "refresh_token"} <= set(r.cookies)
    assert "httponly" in r.headers.get_list("set-cookie")[0].lower()
    assert outbox[-1]["to"] == "ravi@example.com" and "/verify-email?token=" in outbox[-1]["body"]
    assert browser.get("/api/v1/users/me").json()["display_name"] == "Ravi"  # the cookie signs requests in
    assert browser.post("/api/v1/auth/register", json={"email": "ravi@example.com", "password": PASSWORD,
                                                       "display_name": "R"}).status_code == 409
    assert browser.post("/api/v1/auth/register", json={"email": "x@y.z", "password": "short", "display_name": "R"}).status_code == 422

    assert browser.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": "wrong password"}).status_code == 401
    assert browser.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}).status_code == 401
    assert browser.post("/api/v1/auth/login", json={"email": "RAVI@example.com", "password": PASSWORD}).status_code == 200

    first = browser.cookies.get("refresh_token", path="/api/v1/auth")
    assert browser.post("/api/v1/auth/refresh").status_code == 204
    second = browser.cookies.get("refresh_token", path="/api/v1/auth")
    assert second != first
    # Reusing a spent token within a few seconds is another tab refreshing at once: refused, nothing revoked.
    stale = TestClient(app, headers={"X-Requested-With": "test"}, cookies={"refresh_token": first})
    assert stale.post("/api/v1/auth/refresh").status_code == 401
    assert browser.post("/api/v1/auth/refresh").status_code == 204
    # Later, a spent token coming back means it was stolen: the whole session family ends (D25).
    monkeypatch.setattr(service, "REUSE_GRACE", timedelta(0))
    assert stale.post("/api/v1/auth/refresh").status_code == 401
    assert browser.post("/api/v1/auth/refresh").status_code == 401

    assert browser.post("/api/v1/auth/login", json={"email": "ravi@example.com", "password": PASSWORD}).status_code == 200
    assert browser.post("/api/v1/auth/logout").status_code == 204
    assert browser.get("/api/v1/users/me").status_code == 401  # cookies cleared
    assert browser.post("/api/v1/auth/refresh").status_code == 401


def test_email_verification_and_password_reset(browser: TestClient, outbox: list[dict[str, str]]) -> None:
    browser.post("/api/v1/auth/register", json={"email": "mina@example.com", "password": PASSWORD, "display_name": "Mina"})
    verify = link_token(outbox[-1])
    assert browser.post("/api/v1/auth/verify-email", json={"token": "nonsense"}).status_code == 400
    assert browser.post("/api/v1/auth/verify-email", json={"token": verify}).status_code == 204
    assert browser.get("/api/v1/users/me").json()["email_verified"] is True
    assert browser.post("/api/v1/auth/verify-email", json={"token": verify}).status_code == 400  # single use
    assert browser.post("/api/v1/auth/resend-verification").status_code == 409

    sent = len(outbox)
    assert browser.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"}).status_code == 202
    assert len(outbox) == sent  # same answer, no email: nobody learns which addresses have accounts
    assert browser.post("/api/v1/auth/forgot-password", json={"email": "MINA@example.com"}).status_code == 202
    reset = link_token(outbox[-1])
    assert "/reset-password?token=" in outbox[-1]["body"]
    assert browser.post("/api/v1/auth/reset-password", json={"token": reset, "password": "new password 2"}).status_code == 204
    assert browser.post("/api/v1/auth/refresh").status_code == 401  # signed out everywhere
    assert browser.post("/api/v1/auth/reset-password", json={"token": reset, "password": "another one"}).status_code == 400
    assert browser.post("/api/v1/auth/login", json={"email": "mina@example.com", "password": PASSWORD}).status_code == 401
    assert browser.post("/api/v1/auth/login", json={"email": "mina@example.com", "password": "new password 2"}).status_code == 200


def test_tokens_csrf_and_password_hashing(client: TestClient, browser: TestClient) -> None:
    me = client.get("/api/v1/users/me").json()
    assert browser.get("/api/v1/users/me").status_code == 401
    good = security.access_token(uuid.UUID(me["id"]))
    for token in [good[:-1] + ("0" if good[-1] != "0" else "1"),  # tampered signature
                  security.access_token(uuid.UUID(me["id"]), minutes=-1),  # expired
                  f"{me['id']}.99999999999.{'0' * 64}", "garbage"]:
        assert browser.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert browser.get("/api/v1/users/me", headers={"Authorization": f"Bearer {good}"}).status_code == 200

    # Cookie auth: a state-changing request without the custom header (a cross-site form) is refused.
    bare = TestClient(app)
    assert bare.post("/api/v1/workspaces", json={"name": "x"}, headers={"Authorization": f"Bearer {good}"}).status_code == 403
    assert bare.post("/api/v1/auth/login", json={"email": "a@b.c", "password": "x"}).status_code == 403

    stored = security.hash_password("s3cret pass")  # test parameters
    assert security.verify_password("s3cret pass", stored) and not security.verify_password("s3cret pas", stored)
    real = security._scrypt("s3cret pass", b"0" * 16, 2**14, 8, 5)  # the production cost runs (16 MiB, OWASP)
    assert len(real) == 32 and not security.verify_password("x", "!")


def test_login_rate_limit(browser: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    email = f"target-{uuid.uuid4().hex[:8]}@example.com"
    keys = (f"rl:login:{email}", "rl:login-ip:testclient")
    store = redis.Redis.from_url(settings.redis_url)
    store.delete(*keys)
    statuses = [browser.post("/api/v1/auth/login", json={"email": email, "password": "guess"}).status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10 and statuses[10] == 429
    store.delete(*keys)


def test_profile_and_avatar(client: TestClient) -> None:
    me = client.patch("/api/v1/users/me", json={"display_name": "Alice K", "preferred_language": "Hindi",
                                                "academic_level": "B.Tech year 3", "learning_preferences": "Examples first"}).json()
    assert (me["display_name"], me["preferred_language"], me["academic_level"]) == ("Alice K", "Hindi", "B.Tech year 3")
    assert client.patch("/api/v1/users/me", json={"display_name": ""}).status_code == 422

    assert client.put("/api/v1/users/me/avatar", files={"file": ("a.txt", b"not an image", "image/png")}).status_code == 415
    me = client.put("/api/v1/users/me/avatar", files={"file": ("me.png", make_png("A"), "image/png")}).json()
    assert me["avatar_url"].startswith(f"/api/v1/users/{me['id']}/avatar?v=")
    opened = client.get(me["avatar_url"], follow_redirects=False)
    assert opened.status_code == 307 and "X-Amz-Signature" in opened.headers["location"]
    assert client.delete("/api/v1/users/me/avatar").json()["avatar_url"] is None
    assert client.get(f"/api/v1/users/{me['id']}/avatar", follow_redirects=False).status_code == 404


def test_claim_existing_data(client: TestClient, db: Session) -> None:
    """D29: data from the single-user era moves from the placeholder to a real account."""
    legacy = User(email=LEGACY, password_hash="!", display_name="Existing data")
    workspace = Workspace(name="Before accounts")
    db.add_all([legacy, workspace])
    db.flush()
    db.add_all([WorkspaceMember(workspace_id=workspace.id, user_id=legacy.id, role="owner"),
                TutorSession(workspace_id=workspace.id, user_id=legacy.id, title="Old chat")])
    db.flush()
    assert client.post("/api/v1/auth/login", json={"email": LEGACY, "password": "!"}).status_code == 401  # can't log in

    assert claim(db, "alice@example.com") == 1
    mine = client.get("/api/v1/workspaces").json()
    assert [(w["name"], w["role"]) for w in mine] == [("Before accounts", "owner")]
    assert [s["title"] for s in client.get(f"/api/v1/tutor/sessions?workspace_id={workspace.id}").json()] == ["Old chat"]
    with pytest.raises(SystemExit, match="Nothing to claim"):
        claim(db, "alice@example.com")


def test_delete_account(client: TestClient) -> None:
    """§10.5: your account, your private data and the workspaces you own go; others' workspaces stay."""
    mine = client.post("/api/v1/workspaces", json={"name": "Mine"}).json()
    bob = register(client, "bob@example.com", "Bob")
    theirs = client.post("/api/v1/workspaces", json={"name": "Bob's"}, headers=bob).json()
    link = client.post(f"/api/v1/workspaces/{theirs['id']}/invitations", json={"role": "viewer"}, headers=bob).json()
    client.post(f"/api/v1/invitations/{link['url'].rsplit('/', 1)[1]}/accept")
    client.post("/api/v1/tutor/sessions", json={"workspace_id": theirs["id"]})

    assert client.request("DELETE", "/api/v1/users/me", json={"password": "wrong"}).status_code == 403
    assert client.request("DELETE", "/api/v1/users/me", json={"password": PASSWORD}).status_code == 204
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.get(f"/api/v1/workspaces/{mine['id']}", headers=bob).status_code == 404  # gone
    assert [m["user"]["display_name"] for m in client.get(f"/api/v1/workspaces/{theirs['id']}/members", headers=bob).json()] == ["Bob"]
