"""Passwords and tokens (PRD A2, docs/decisions.md D25–D26). Stdlib only."""

import base64
import hashlib
import hmac
import secrets
import time
import uuid

from app.config import settings

SECRET = (settings.secret_key or secrets.token_hex(32)).encode()
# OWASP scrypt parameters (N=2^14, r=8, p=5): ~16 MiB, a few hundred ms per check.
N, R, P = 2**14, 8, 5


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=64 * 1024 * 1024, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, N, R, P)
    return f"scrypt${N}${R}${P}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
    except ValueError:
        return False  # e.g. "!" for accounts that can't log in
    if scheme != "scrypt":
        return False
    return hmac.compare_digest(_scrypt(password, base64.b64decode(salt), int(n), int(r), int(p)), base64.b64decode(digest))


def access_token(user_id: uuid.UUID, minutes: int | None = None) -> str:
    """`<user id>.<expiry>.<signature>`: HMAC-SHA256 over the first two parts."""
    body = f"{user_id}.{int(time.time()) + 60 * (minutes or settings.access_token_minutes)}"
    return f"{body}.{hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()}"


def read_access_token(token: str) -> uuid.UUID | None:
    body, _, signature = token.rpartition(".")
    if not hmac.compare_digest(hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest(), signature):
        return None
    user_id, _, expires = body.partition(".")
    try:
        return uuid.UUID(user_id) if int(expires) > time.time() else None
    except ValueError:
        return None


def new_token() -> tuple[str, str]:
    """A random secret for refresh, email and invitation links, and the hash that gets stored."""
    token = secrets.token_urlsafe(32)
    return token, token_hash(token)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
