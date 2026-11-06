import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import mail, security, storage
from app.core.exceptions import AppError, NotFoundError
from app.core.permissions import ROLES, Access
from app.core.ratelimit import limit
from app.modules.documents.models import Document
from app.modules.users import service as users
from app.modules.users.models import AuditLog, User
from app.modules.workspaces import repository
from app.modules.workspaces.models import Invitation, Workspace, WorkspaceMember
from app.modules.workspaces.schemas import (
    AuditOut,
    InvitationCreated,
    InvitationIn,
    InvitationOut,
    InvitationPreview,
    MemberOut,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)

log = logging.getLogger(__name__)


def _out(workspace: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut.model_validate(workspace).model_copy(update={"role": role})


def list_mine(db: Session, user: User) -> list[WorkspaceOut]:
    rows = db.execute(select(Workspace, WorkspaceMember.role).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
                      .where(WorkspaceMember.user_id == user.id).order_by(Workspace.created_at.desc()))
    return [_out(w, role) for w, role in rows]


def get(db: Session, workspace_id: uuid.UUID) -> Workspace:
    workspace = repository.get(db, workspace_id)
    if workspace is None:
        raise NotFoundError("Workspace")
    return workspace


def detail(db: Session, access: Access) -> WorkspaceOut:
    return _out(get(db, access.workspace_id), access.role)


def create(db: Session, user: User, data: WorkspaceCreate) -> WorkspaceOut:
    workspace = repository.add(db, Workspace(**data.model_dump()))
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    users.audit(db, "workspace.created", user_id=user.id, workspace_id=workspace.id, target=workspace.name)
    db.commit()
    return _out(workspace, "owner")


def update(db: Session, access: Access, data: WorkspaceUpdate) -> WorkspaceOut:
    workspace = get(db, access.workspace_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(workspace, field, value)
    db.commit()
    return _out(workspace, access.role)


def delete(db: Session, access: Access) -> None:
    # Rows go via ON DELETE CASCADE (members' private data too, A13); stored files don't, so remove them after.
    workspace = get(db, access.workspace_id)
    keys = list(db.scalars(select(Document.storage_key).where(Document.workspace_id == workspace.id)))
    users.audit(db, "workspace.deleted", user_id=access.user.id, workspace_id=workspace.id, target=workspace.name)
    repository.delete(db, workspace)
    db.commit()
    for key in keys:
        try:
            storage.delete(key)
        except Exception:
            log.warning("workspace %s deleted but its stored file %s could not be removed", workspace.id, key)


# --- Members (A11) --------------------------------------------------------------------------------------------------


def members(db: Session, workspace_id: uuid.UUID) -> list[MemberOut]:
    rows = db.execute(select(WorkspaceMember, User).join(User, User.id == WorkspaceMember.user_id)
                      .where(WorkspaceMember.workspace_id == workspace_id))
    out = [MemberOut(user=users.person(u), role=m.role, joined_at=m.created_at) for m, u in rows]  # type: ignore[arg-type]
    return sorted(out, key=lambda m: (-ROLES.index(m.role), m.user.display_name.lower()))


def _member(db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMember:
    member = db.get(WorkspaceMember, (workspace_id, user_id))
    if member is None:
        raise NotFoundError("Member")
    return member


def _may_manage(access: Access, *roles: str) -> None:
    """A11: admins manage editors and viewers; only the owner manages admins; nobody changes the owner."""
    if "owner" in roles:
        raise AppError(403, "The owner's membership can't be changed.")
    needed = "owner" if "admin" in roles else "admin"
    if not access.at_least(needed):
        raise AppError(403, f"Only the {'owner' if needed == 'owner' else 'owner and admins'} can do this.")


def change_role(db: Session, access: Access, user_id: uuid.UUID, role: str) -> MemberOut:
    member = _member(db, access.workspace_id, user_id)
    _may_manage(access, member.role, role)
    user = db.get(User, user_id)
    assert user is not None  # FK
    users.audit(db, "member.role_changed", user_id=access.user.id, workspace_id=access.workspace_id, target=user.email,
                old=member.role, new=role)
    member.role = role
    db.commit()
    return MemberOut(user=users.person(user), role=role, joined_at=member.created_at)  # type: ignore[arg-type]


def remove(db: Session, access: Access, user_id: uuid.UUID) -> None:
    """Remove a member, or leave (any member). Their private data stays but is unreachable until they rejoin (A13)."""
    member = _member(db, access.workspace_id, user_id)
    if user_id == access.user.id:
        if member.role == "owner":
            raise AppError(409, "The owner can't leave. Delete the workspace instead.")
    else:
        _may_manage(access, member.role)
    user = db.get(User, user_id)
    users.audit(db, "member.left" if user_id == access.user.id else "member.removed", user_id=access.user.id,
                workspace_id=access.workspace_id, target=user.email if user else "", role=member.role)
    db.delete(member)
    db.commit()


# --- Invitations (B3, A12) ------------------------------------------------------------------------------------------


def _active(now: datetime):  # type: ignore[no-untyped-def]
    return (Invitation.revoked_at.is_(None), Invitation.expires_at > now,
            Invitation.max_uses.is_(None) | (Invitation.uses < Invitation.max_uses))


def invitations(db: Session, workspace_id: uuid.UUID) -> list[Invitation]:
    return list(db.scalars(select(Invitation).where(Invitation.workspace_id == workspace_id, *_active(datetime.now(UTC)))
                           .order_by(Invitation.created_at.desc())))


def invite(db: Session, access: Access, data: InvitationIn) -> InvitationCreated:
    _may_manage(access, data.role)
    limit(f"invite:{access.user.id}", 50, 3600)
    workspace = get(db, access.workspace_id)
    email = data.email.lower() if data.email else None
    if email and db.scalar(select(User.id).join(WorkspaceMember, WorkspaceMember.user_id == User.id).where(
            WorkspaceMember.workspace_id == workspace.id, User.email == email)):
        raise AppError(409, f"{email} is already a member.")
    token, hashed = security.new_token()
    invitation = Invitation(workspace_id=workspace.id, email=email, role=data.role, token_hash=hashed,
                            created_by=access.user.id, expires_at=datetime.now(UTC) + timedelta(days=data.expires_in_days),
                            max_uses=1 if email else data.max_uses, uses=0)
    db.add(invitation)
    users.audit(db, "invitation.created", user_id=access.user.id, workspace_id=workspace.id, target=email or "link",
                role=data.role)
    db.commit()
    url = f"{settings.app_url}/invite/{token}"
    emailed = bool(email) and mail.send(
        email,  # type: ignore[arg-type]
        f"{access.user.display_name} invited you to “{workspace.name}” on Karaage",
        f"{access.user.display_name} invited you to join the workspace “{workspace.name}” as {data.role}.\n\n"
        f"Accept the invitation:\n{url}\n\nSign in or create an account with this email address ({email}). "
        f"The link expires in {data.expires_in_days} days.")
    return InvitationCreated(**InvitationOut.model_validate(invitation).model_dump(), url=url, emailed=emailed)


def revoke(db: Session, access: Access, invitation_id: uuid.UUID) -> None:
    invitation = db.get(Invitation, invitation_id)
    if invitation is None or invitation.workspace_id != access.workspace_id:
        raise NotFoundError("Invitation")
    _may_manage(access, invitation.role)
    invitation.revoked_at = datetime.now(UTC)
    users.audit(db, "invitation.revoked", user_id=access.user.id, workspace_id=access.workspace_id,
                target=invitation.email or "link", role=invitation.role)
    db.commit()


def _by_token(db: Session, token: str, *, lock: bool = False) -> Invitation:
    query = select(Invitation).where(Invitation.token_hash == security.token_hash(token))
    invitation = db.scalar(query.with_for_update() if lock else query)
    if invitation is None:
        raise NotFoundError("Invitation")
    if not db.scalar(select(Invitation.id).where(Invitation.id == invitation.id, *_active(datetime.now(UTC)))):
        raise AppError(410, "This invitation has expired, been used up or been revoked. Ask for a new one.")
    return invitation


def preview(db: Session, token: str) -> InvitationPreview:
    invitation = _by_token(db, token)
    inviter = db.get(User, invitation.created_by) if invitation.created_by else None
    return InvitationPreview(workspace_name=get(db, invitation.workspace_id).name, role=invitation.role,  # type: ignore[arg-type]
                             invited_by=inviter.display_name if inviter else None, email=invitation.email)


def accept(db: Session, user: User, token: str) -> WorkspaceOut:
    invitation = _by_token(db, token, lock=True)
    if invitation.email and invitation.email != user.email:
        raise AppError(403, f"This invitation is for {invitation.email}. Sign in with that account to accept it.")
    if invitation.email and not user.email_verified_at:
        raise AppError(403, "Confirm your email address first (check your inbox), then open the invitation again.")
    workspace = get(db, invitation.workspace_id)
    if existing := db.get(WorkspaceMember, (workspace.id, user.id)):
        return _out(workspace, existing.role)  # already a member: keep the current role
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=invitation.role))
    invitation.uses += 1
    users.audit(db, "member.joined", user_id=user.id, workspace_id=workspace.id, target=user.email,
                role=invitation.role, via="email" if invitation.email else "link")
    db.commit()
    return _out(workspace, invitation.role)


def audit_log(db: Session, workspace_id: uuid.UUID, limit_rows: int = 100) -> list[AuditOut]:
    rows = db.execute(select(AuditLog, User.display_name).outerjoin(User, User.id == AuditLog.user_id)
                      .where(AuditLog.workspace_id == workspace_id).order_by(AuditLog.id.desc()).limit(limit_rows))
    return [AuditOut(action=a.action, actor=name, target=a.target, details=a.details, created_at=a.created_at) for a, name in rows]
