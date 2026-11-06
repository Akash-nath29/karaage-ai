import uuid

from sqlalchemy.orm import Session

from app.modules.workspaces.models import Workspace


def get(db: Session, workspace_id: uuid.UUID) -> Workspace | None:
    return db.get(Workspace, workspace_id)


def add(db: Session, workspace: Workspace) -> Workspace:
    db.add(workspace)
    db.flush()
    return workspace


def delete(db: Session, workspace: Workspace) -> None:
    db.delete(workspace)
