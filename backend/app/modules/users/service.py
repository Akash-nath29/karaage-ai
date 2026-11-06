"""Accounts, sessions and profiles (PRD Module A, docs/decisions.md D25–D26, D34)."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core import mail, security, storage
from app.core.exceptions import AppError, NotFoundError
from app.core.ratelimit import limit
from app.modules.users.models import AuditLog, EmailToken, RefreshToken, User
from app.modules.users.schemas import LoginIn, PersonOut, ProfilePatch, RegisterIn, ResetIn, UserOut

log = logging.getLogger(__name__)
# Rate limits (§10.4): per account strict, per IP generous, because a campus network puts a whole class behind one IP.
REUSE_GRACE = timedelta(seconds=30)  # two tabs refreshing at once isn't theft (cookies are shared across tabs)
ENDED = "Your session has ended. Sign in again."
AVATAR_TYPES = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}
AVATAR_MAX_BYTES = 2 * 1024 * 1024


def audit(db: Session, action: str, *, user_id: uuid.UUID | None = None, workspace_id: uuid.UUID | None = None,
          target: str = "", ip: str | None = None, **details: Any) -> None:
    """Record a security-relevant action (PRD §10.4). The caller commits."""
    db.add(AuditLog(action=action, user_id=user_id, workspace_id=workspace_id, target=target[:320], ip=ip, details=details))


def avatar_url(user: User) -> str | None:
    # The key changes on every upload, so the URL does too and browsers never show a stale picture.
    return f"/api/v1/users/{user.id}/avatar?v={user.avatar_key.rsplit('/', 1)[-1]}" if user.avatar_key else None


def out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, display_name=user.display_name, avatar_url=avatar_url(user),
                   preferred_language=user.preferred_language, academic_level=user.academic_level,
                   learning_preferences=user.learning_preferences, email_verified=user.email_verified_at is not None,
                   created_at=user.created_at)


def person(user: User) -> PersonOut:
    return PersonOut(id=user.id, email=user.email, display_name=user.display_name, avatar_url=avatar_url(user))


def _email(raw: str) -> str:
    return raw.strip().lower()


def _now() -> datetime:
    return datetime.now(UTC)


# --- Sessions -------------------------------------------------------------------------------------------------------


def _issue(db: Session, user_id: uuid.UUID, family_id: uuid.UUID) -> str:
    token, hashed = security.new_token()
    db.add(RefreshToken(user_id=user_id, family_id=family_id, token_hash=hashed,
                        expires_at=_now() + timedelta(days=settings.refresh_token_days)))
    return token


@cache
def _dummy_hash() -> str:
    return security.hash_password("timing-equaliser")


def register(db: Session, data: RegisterIn, ip: str | None) -> tuple[User, str]:
    limit(f"register:{ip}", 100, 3600)
    email = _email(data.email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "An account with this email already exists. Sign in instead.")
    user = User(id=uuid.uuid4(), email=email, password_hash=security.hash_password(data.password),
                display_name=data.display_name, created_at=_now())
    db.add(user)
    db.flush()
    refresh = _issue(db, user.id, uuid.uuid4())
    audit(db, "auth.register", user_id=user.id, target=email, ip=ip)
    db.commit()
    send_verification(db, user)
    return user, refresh


def login(db: Session, data: LoginIn, ip: str | None) -> tuple[User, str]:
    email = _email(data.email)
    limit(f"login-ip:{ip}", 300, 300)
    limit(f"login:{email}", 10, 900)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        security.verify_password(data.password, _dummy_hash())  # same timing whether or not the account exists
    if user is None or not security.verify_password(data.password, user.password_hash):
        audit(db, "auth.login_failed", user_id=user.id if user else None, target=email, ip=ip)
        db.commit()
        raise AppError(401, "Wrong email or password.")
    refresh = _issue(db, user.id, uuid.uuid4())
    audit(db, "auth.login", user_id=user.id, ip=ip)
    db.commit()
    return user, refresh


def _revoke(db: Session, *where: Any) -> None:
    db.execute(update(RefreshToken).where(*where, RefreshToken.revoked_at.is_(None)).values(revoked_at=_now()))


def refresh(db: Session, token: str | None, ip: str | None) -> tuple[uuid.UUID, str]:
    """Rotate: the presented token is spent and a new one issued in the same family (D25)."""
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == security.token_hash(token))
                    .with_for_update()) if token else None
    now = _now()
    if row is None or row.revoked_at or row.expires_at <= now:
        raise AppError(401, ENDED)
    if row.used_at:
        if now - row.used_at > REUSE_GRACE:  # a spent token came back: assume it was stolen, end every session
            _revoke(db, RefreshToken.family_id == row.family_id)
            audit(db, "auth.refresh_reuse", user_id=row.user_id, ip=ip)
            db.commit()
        raise AppError(401, ENDED)
    row.used_at = now
    new = _issue(db, row.user_id, row.family_id)
    db.commit()
    return row.user_id, new


def logout(db: Session, token: str | None) -> None:
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == security.token_hash(token))) if token else None
    if row:
        _revoke(db, RefreshToken.family_id == row.family_id)
        db.commit()


# --- Email links ----------------------------------------------------------------------------------------------------


def _email_token(db: Session, user: User, purpose: str, hours: int) -> str:
    token, hashed = security.new_token()
    db.add(EmailToken(user_id=user.id, purpose=purpose, token_hash=hashed, expires_at=_now() + timedelta(hours=hours)))
    db.commit()
    return token


def send_verification(db: Session, user: User) -> bool:
    token = _email_token(db, user, "verify", 24)
    return mail.send(user.email, "Confirm your email for Karaage",
                     f"Hi {user.display_name},\n\nConfirm your email address:\n{settings.app_url}/verify-email?token={token}\n\n"
                     "The link works for 24 hours. If you didn't create a Karaage account, ignore this email.")


def resend_verification(db: Session, user: User) -> None:
    if user.email_verified_at:
        raise AppError(409, "Your email is already confirmed.")
    limit(f"verify:{user.id}", 5, 3600)
    if not send_verification(db, user):
        raise AppError(503, "The email couldn't be sent. Try again in a few minutes.")


def _use(db: Session, token: str, purpose: str) -> User:
    row = db.scalar(select(EmailToken).where(EmailToken.token_hash == security.token_hash(token),
                                             EmailToken.purpose == purpose).with_for_update())
    if row is None or row.used_at or row.expires_at <= _now():
        raise AppError(400, "This link is invalid or has expired. Ask for a new one.")
    row.used_at = _now()
    user = db.get(User, row.user_id)
    assert user is not None  # FK
    return user


def verify_email(db: Session, token: str) -> None:
    user = _use(db, token, "verify")
    user.email_verified_at = user.email_verified_at or _now()
    audit(db, "auth.email_verified", user_id=user.id)
    db.commit()


def forgot_password(db: Session, email: str, ip: str | None) -> None:
    """Same answer whether or not the account exists (no account discovery)."""
    email = _email(email)
    limit(f"forgot-ip:{ip}", 50, 3600)
    limit(f"forgot:{email}", 3, 3600)
    user = db.scalar(select(User).where(User.email == email))
    if user and user.password_hash != "!":
        token = _email_token(db, user, "reset", 1)
        mail.send(user.email, "Reset your Karaage password",
                  f"Hi {user.display_name},\n\nChoose a new password:\n{settings.app_url}/reset-password?token={token}\n\n"
                  "The link works for 1 hour. If you didn't ask for this, ignore this email: your password stays the same.")


def reset_password(db: Session, data: ResetIn, ip: str | None) -> None:
    user = _use(db, data.token, "reset")
    user.password_hash = security.hash_password(data.password)
    user.email_verified_at = user.email_verified_at or _now()  # the link proved they own the address
    _revoke(db, RefreshToken.user_id == user.id)  # sign out everywhere
    audit(db, "auth.password_reset", user_id=user.id, ip=ip)
    db.commit()


def delete_account(db: Session, user: User, password: str) -> None:
    """§10.5: people can delete their own data. Workspaces they own go too (with everything in them, A13); their
    private data elsewhere goes by cascade. Shared content they made (documents, lessons) stays with the workspace."""
    from app.core.permissions import Access  # noqa: PLC0415  (permissions imports this module's models)
    from app.modules.workspaces import service as workspaces  # noqa: PLC0415
    from app.modules.workspaces.models import WorkspaceMember  # noqa: PLC0415

    if not security.verify_password(password, user.password_hash):
        raise AppError(403, "That password isn't right.")
    owned = list(db.scalars(select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == user.id, WorkspaceMember.role == "owner")))
    for workspace_id in owned:
        workspaces.delete(db, Access(user, workspace_id, "owner"))
    audit(db, "auth.account_deleted", user_id=user.id, target=user.email, workspaces=len(owned))
    db.delete(user)
    db.commit()
    _drop_file(user.avatar_key)


# --- Profile (A3) ---------------------------------------------------------------------------------------------------


def update_profile(db: Session, user: User, patch: ProfilePatch) -> User:
    for field, value in patch.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    return user


def _drop_file(key: str | None) -> None:
    if key:
        try:
            storage.delete(key)
        except Exception:
            log.warning("could not remove old avatar %s", key)


def set_avatar(db: Session, user: User, data: bytes) -> User:
    if len(data) > AVATAR_MAX_BYTES:
        raise AppError(413, "The picture is larger than 2 MB.")
    content_type = next((t for magic, t in AVATAR_TYPES.items() if data.startswith(magic)), None)
    if content_type is None:
        raise AppError(415, "Use a PNG or JPEG picture.")
    old, user.avatar_key = user.avatar_key, f"avatars/{user.id}/{uuid.uuid4().hex}"
    storage.put(user.avatar_key, data, content_type)
    db.commit()
    _drop_file(old)
    return user


def remove_avatar(db: Session, user: User) -> User:
    old, user.avatar_key = user.avatar_key, None
    db.commit()
    _drop_file(old)
    return user


def avatar_file_url(db: Session, user_id: uuid.UUID) -> str:
    user = db.get(User, user_id)
    if user is None or not user.avatar_key:
        raise NotFoundError("Picture")
    return storage.presigned_url(user.avatar_key, "avatar")
