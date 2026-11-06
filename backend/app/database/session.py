from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Connection, DateTime, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


RLS_ROLE = "semsaviour_rls"  # created by the multi_user migration


def row_security(connection: Connection, user_id: object) -> None:
    """Row-level security for this transaction (D27): policies see app.user_id, and the non-superuser role makes
    Postgres apply them at all (superusers bypass RLS). Transaction-local: a pooled connection never carries it
    into the next request."""
    connection.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})
    connection.execute(text(f"SET LOCAL ROLE {RLS_ROLE}"))


@event.listens_for(Session, "after_begin")
def _row_security(session: Session, _transaction: object, connection: Connection) -> None:
    # API sessions act as their user in every transaction (core.permissions.act_as sets these).
    if session.info.get("rls"):
        row_security(connection, session.info["user_id"])


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


def get_db() -> Iterator[Session]:
    # Services commit explicitly; anything uncommitted is rolled back on close.
    with SessionLocal() as db:
        yield db


def get_session_factory() -> Callable[[], Session]:
    # For long-lived streams (SSE) that open a fresh short session per poll instead of holding one.
    return SessionLocal


DbSession = Annotated[Session, Depends(get_db)]
SessionFactory = Annotated[Callable[[], Session], Depends(get_session_factory)]
