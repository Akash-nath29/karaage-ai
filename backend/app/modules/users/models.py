import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lower-case
    password_hash: Mapped[str] = mapped_column(String(200))  # "!" = can't log in (the legacy placeholder, D29)
    display_name: Mapped[str] = mapped_column(String(100))
    avatar_key: Mapped[str | None] = mapped_column(String(200))
    # Profile (A3). The tutor answers in the preferred language (A15).
    preferred_language: Mapped[str] = mapped_column(String(50), default="English")
    academic_level: Mapped[str] = mapped_column(String(100), default="")
    learning_preferences: Mapped[str] = mapped_column(Text, default="")
    email_verified_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class RefreshToken(Base):
    """One per refresh: rotated on use. Reusing a used one revokes its family (every session descended from the
    same login), because only a thief would still hold an old token (D25)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class EmailToken(Base):
    """Single-use links: email verification (24 h) and password reset (1 h)."""

    __tablename__ = "email_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(10))  # verify | reset
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuditLog(Base):
    """Security-relevant actions (PRD §10.4). No foreign keys: the record outlives what it describes."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)  # who did it
    action: Mapped[str] = mapped_column(String(50))  # e.g. member.role_changed
    target: Mapped[str] = mapped_column(String(320), default="")  # e.g. the email or file affected
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(server_default=func.clock_timestamp())
