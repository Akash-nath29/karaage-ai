import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Workspace(Base):
    # ponytail: no visibility column; A5 allows only "private", so there's nothing to store yet.
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class WorkspaceMember(Base):
    """Membership and role (PRD §4.2, A11). Exactly one owner per workspace."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        Index("uq_workspace_members_one_owner", "workspace_id", unique=True, postgresql_where=text("role = 'owner'")),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(10))  # owner | admin | editor | viewer
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Invitation(Base):
    """B3/A12. With `email`: only that (verified) address can accept. Without: a link anyone signed in can use,
    up to max_uses. The token is shown once; only its hash is stored."""

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(10))  # admin | editor | viewer (never owner)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime]
    max_uses: Mapped[int | None]  # None = unlimited until it expires (link invites)
    uses: Mapped[int] = mapped_column(default=0)
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
