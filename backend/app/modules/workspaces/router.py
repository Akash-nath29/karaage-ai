import uuid

from fastapi import APIRouter

from app.core.permissions import Admin, CurrentUser, Owner, Viewer
from app.database.session import DbSession
from app.modules.workspaces import service
from app.modules.workspaces.models import Invitation
from app.modules.workspaces.schemas import (
    AuditOut,
    InvitationCreated,
    InvitationIn,
    InvitationOut,
    InvitationPreview,
    MemberOut,
    RoleIn,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
invitations_router = APIRouter(prefix="/invitations", tags=["workspaces"])


@router.post("", response_model=WorkspaceOut, status_code=201)
def create_workspace(data: WorkspaceCreate, user: CurrentUser, db: DbSession) -> WorkspaceOut:
    """You become its owner."""
    return service.create(db, user, data)


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(user: CurrentUser, db: DbSession) -> list[WorkspaceOut]:
    """Workspaces you're a member of, with your role in each."""
    return service.list_mine(db, user)


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: uuid.UUID, access: Viewer, db: DbSession) -> WorkspaceOut:
    return service.detail(db, access)


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(workspace_id: uuid.UUID, data: WorkspaceUpdate, access: Admin, db: DbSession) -> WorkspaceOut:
    return service.update(db, access, data)


@router.delete("/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: uuid.UUID, access: Owner, db: DbSession) -> None:
    service.delete(db, access)


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_members(workspace_id: uuid.UUID, _: Viewer, db: DbSession) -> list[MemberOut]:
    return service.members(db, workspace_id)


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberOut)
def change_role(workspace_id: uuid.UUID, user_id: uuid.UUID, data: RoleIn, access: Admin, db: DbSession) -> MemberOut:
    return service.change_role(db, access, user_id, data.role)


@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
def remove_member(workspace_id: uuid.UUID, user_id: uuid.UUID, access: Viewer, db: DbSession) -> None:
    """Remove someone (owner/admins, A11), or leave the workspace (your own id)."""
    service.remove(db, access, user_id)


@router.post("/{workspace_id}/invitations", response_model=InvitationCreated, status_code=201)
def invite(workspace_id: uuid.UUID, data: InvitationIn, access: Admin, db: DbSession) -> InvitationCreated:
    return service.invite(db, access, data)


@router.get("/{workspace_id}/invitations", response_model=list[InvitationOut])
def list_invitations(workspace_id: uuid.UUID, _: Admin, db: DbSession) -> list[Invitation]:
    """Invitations that can still be accepted."""
    return service.invitations(db, workspace_id)


@router.delete("/{workspace_id}/invitations/{invitation_id}", status_code=204)
def revoke_invitation(workspace_id: uuid.UUID, invitation_id: uuid.UUID, access: Admin, db: DbSession) -> None:
    service.revoke(db, access, invitation_id)


@router.get("/{workspace_id}/audit", response_model=list[AuditOut])
def audit_log(workspace_id: uuid.UUID, _: Admin, db: DbSession) -> list[AuditOut]:
    """Recent security-relevant actions in this workspace (PRD §10.4)."""
    return service.audit_log(db, workspace_id)


@invitations_router.get("/{token}", response_model=InvitationPreview)
def preview_invitation(token: str, db: DbSession) -> InvitationPreview:
    """Public, so the invite page can say what you're joining before you sign in."""
    return service.preview(db, token)


@invitations_router.post("/{token}/accept", response_model=WorkspaceOut)
def accept_invitation(token: str, user: CurrentUser, db: DbSession) -> WorkspaceOut:
    return service.accept(db, user, token)
