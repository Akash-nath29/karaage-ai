import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.documents.models import Document


def list_for_workspace(db: Session, workspace_id: uuid.UUID, course_id: uuid.UUID | None) -> Sequence[Document]:
    query = select(Document).where(Document.workspace_id == workspace_id)
    if course_id:
        query = query.where(Document.course_id == course_id)
    return db.scalars(query.order_by(Document.created_at.desc())).all()


def get(db: Session, document_id: uuid.UUID) -> Document | None:
    return db.get(Document, document_id)


def find_by_checksum(db: Session, workspace_id: uuid.UUID, checksum: str) -> Document | None:
    return db.scalar(select(Document).where(Document.workspace_id == workspace_id, Document.checksum == checksum))


def add(db: Session, document: Document) -> Document:
    db.add(document)
    db.flush()
    return document


def delete(db: Session, document: Document) -> None:
    db.delete(document)
