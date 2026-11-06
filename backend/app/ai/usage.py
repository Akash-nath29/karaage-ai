"""AI consumption log (PRD §12). Recorded for every provider call from day one (docs/decisions.md D4).
The person is whoever the session acts for (`db.info["user_id"]`: the request's user, or a job's requester, D30)."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import BigInteger, Identity, String, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.config import settings
from app.core.exceptions import AppError
from app.database.session import Base


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(index=True)  # no FK: cost history outlives workspaces
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)  # no FK, same reason
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    operation: Mapped[str] = mapped_column(String(50))  # e.g. embed_documents, embed_query
    input_tokens: Mapped[int]  # estimated for embeddings: Gemini's embed API reports no usage
    output_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


def _month_start() -> datetime:
    return datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


_TOKENS = func.coalesce(func.sum(LlmUsage.input_tokens + LlmUsage.output_tokens), 0)
_CHAT = LlmUsage.operation.not_like("embed%")  # budgets count chat tokens (D21)


def check_budget(db: Session, workspace_id: uuid.UUID | None, *, searches: int = 0) -> None:
    """Stop before a workspace or a person exceeds the monthly AI budget (A18, §12.6). Raises a user-facing error."""
    month = LlmUsage.created_at >= _month_start()
    user_id = db.info.get("user_id")
    if user_id and settings.user_monthly_tokens:
        used = db.scalar(select(_TOKENS).where(LlmUsage.user_id == user_id, month, _CHAT))
        if used >= settings.user_monthly_tokens:
            raise AppError(429, f"You've used your monthly AI allowance ({used:,} of {settings.user_monthly_tokens:,} "
                                "tokens). It resets on the 1st; an admin can raise USER_MONTHLY_TOKENS.")
    if workspace_id is None:
        return
    this_month = (LlmUsage.workspace_id == workspace_id, month)
    if settings.workspace_monthly_tokens:
        used = db.scalar(select(_TOKENS).where(*this_month, _CHAT))
        if used >= settings.workspace_monthly_tokens:
            raise AppError(429, f"This workspace has used its monthly AI budget ({used:,} of "
                                f"{settings.workspace_monthly_tokens:,} tokens). Raise WORKSPACE_MONTHLY_TOKENS to continue.")
    if searches and settings.workspace_monthly_searches:
        used = db.scalar(select(func.count()).select_from(LlmUsage).where(*this_month, LlmUsage.operation == "web_search"))
        if used + searches > settings.workspace_monthly_searches:
            raise AppError(429, f"This workspace has used its monthly web-search budget ({used} of "
                                f"{settings.workspace_monthly_searches}). Raise WORKSPACE_MONTHLY_SEARCHES to continue.")


def record(
    db: Session,
    *,
    workspace_id: uuid.UUID | None,
    provider: str,
    model: str,
    operation: str,
    input_tokens: int,
    output_tokens: int = 0,
) -> None:
    db.add(
        LlmUsage(
            workspace_id=workspace_id,
            user_id=db.info.get("user_id"),
            provider=provider,
            model=model,
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )


# --- Usage dashboards (Phase 6, D30) -------------------------------------------------------------------------------


class OperationUsage(BaseModel):
    operation: str
    calls: int
    tokens: int


class MemberUsage(BaseModel):
    user_id: uuid.UUID | None
    name: str  # display name, or "Removed user" / "System"
    tokens: int
    searches: int


class WorkspaceUsage(BaseModel):
    month_start: datetime
    tokens: int  # chat tokens this month
    token_budget: int  # 0 = unlimited
    searches: int
    search_budget: int
    embedding_tokens: int
    by_operation: list[OperationUsage]
    by_member: list[MemberUsage] | None  # admins and the owner only


class WorkspaceShare(BaseModel):
    workspace_id: uuid.UUID
    name: str
    tokens: int


class MyUsage(BaseModel):
    month_start: datetime
    tokens: int
    token_budget: int
    searches: int
    by_workspace: list[WorkspaceShare]


def workspace_usage(db: Session, workspace_id: uuid.UUID, *, members: dict[uuid.UUID, str] | None) -> WorkspaceUsage:
    """`members` (id → name) adds the per-person breakdown."""
    where = (LlmUsage.workspace_id == workspace_id, LlmUsage.created_at >= _month_start())
    ops = db.execute(select(LlmUsage.operation, func.count(), _TOKENS).where(*where).group_by(LlmUsage.operation)
                     .order_by(_TOKENS.desc())).all()
    by_op = [OperationUsage(operation=op, calls=calls, tokens=tokens) for op, calls, tokens in ops]
    chat = [o for o in by_op if not o.operation.startswith("embed")]
    per_member: list[MemberUsage] | None = None
    if members is not None:
        rows = db.execute(select(
            LlmUsage.user_id,
            func.coalesce(func.sum(LlmUsage.input_tokens + LlmUsage.output_tokens).filter(_CHAT), 0),
            func.count().filter(LlmUsage.operation == "web_search"),
        ).where(*where).group_by(LlmUsage.user_id)).all()
        per_member = sorted((MemberUsage(user_id=u, name=members.get(u, "Removed user") if u else "System", tokens=t,
                                         searches=s) for u, t, s in rows), key=lambda m: -m.tokens)
    return WorkspaceUsage(
        month_start=_month_start(), tokens=sum(o.tokens for o in chat), token_budget=settings.workspace_monthly_tokens,
        searches=next((o.calls for o in by_op if o.operation == "web_search"), 0),
        search_budget=settings.workspace_monthly_searches,
        embedding_tokens=sum(o.tokens for o in by_op if o.operation.startswith("embed")),
        by_operation=by_op, by_member=per_member)


def my_usage(db: Session, user_id: uuid.UUID, names: dict[uuid.UUID, str]) -> MyUsage:
    """`names`: the user's workspaces (id → name); usage in workspaces they've left is counted but not itemised."""
    where = (LlmUsage.user_id == user_id, LlmUsage.created_at >= _month_start())
    per_ws = db.execute(select(LlmUsage.workspace_id, _TOKENS).where(*where, _CHAT).group_by(LlmUsage.workspace_id)).all()
    return MyUsage(
        month_start=_month_start(), tokens=db.scalar(select(_TOKENS).where(*where, _CHAT)) or 0,
        token_budget=settings.user_monthly_tokens,
        searches=db.scalar(select(func.count()).select_from(LlmUsage).where(*where, LlmUsage.operation == "web_search")) or 0,
        by_workspace=sorted((WorkspaceShare(workspace_id=w, name=names[w], tokens=t) for w, t in per_ws if w in names),
                            key=lambda s: -s.tokens))
