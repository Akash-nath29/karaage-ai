"""research created_at clock_timestamp

Revision ID: a1cc70564ae3
Revises: 43fc548f645a
Create Date: 2026-11-06 00:04:27.245461
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1cc70564ae3'
down_revision: str | None = '43fc548f645a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # "Latest research run" orders by created_at; now() is the transaction start time, so two runs in one
    # transaction would tie. clock_timestamp() is the actual time of the insert.
    op.alter_column("research_jobs", "created_at", server_default=sa.text("clock_timestamp()"))


def downgrade() -> None:
    op.alter_column("research_jobs", "created_at", server_default=sa.text("now()"))
