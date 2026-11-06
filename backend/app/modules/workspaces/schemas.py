import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.users.schemas import PersonOut

Role = Literal["owner", "admin", "editor", "viewer"]
InviteRole = Literal["admin", "editor", "viewer"]  # nobody is invited as owner (A12)


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)


class WorkspaceUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    created_at: datetime
    role: Role = "viewer"  # yours


class MemberOut(BaseModel):
    user: PersonOut
    role: Role
    joined_at: datetime


class RoleIn(BaseModel):
    role: InviteRole


class InvitationIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # With an email: sent to that address, single use, only that verified account can accept.
    # Without: a link to share, usable max_uses times (unlimited if null) until it expires.
    email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: InviteRole = "viewer"
    expires_in_days: int = Field(default=7, ge=1, le=30)
    max_uses: int | None = Field(default=None, ge=1, le=1000)


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    role: InviteRole
    expires_at: datetime
    max_uses: int | None
    uses: int
    created_at: datetime


class InvitationCreated(InvitationOut):
    url: str  # shown once: only the token's hash is stored
    emailed: bool


class InvitationPreview(BaseModel):
    workspace_name: str
    role: InviteRole
    invited_by: str | None
    email: str | None  # set when only that address can accept


class AuditOut(BaseModel):
    action: str
    actor: str | None
    target: str
    details: dict[str, Any]
    created_at: datetime
