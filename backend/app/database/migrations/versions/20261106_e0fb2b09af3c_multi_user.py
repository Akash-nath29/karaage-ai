"""multi_user: users, sessions, members, invitations, audit log, per-user data, row-level security

Existing data (single-user era) goes to a placeholder account that can't log in; `python -m scripts.claim_data`
hands it to a real one (docs/decisions.md D29). RLS: D27.

Revision ID: e0fb2b09af3c
Revises: 6c25110df951
Create Date: 2026-11-06 12:05:14.210480
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e0fb2b09af3c'
down_revision: str | None = '6c25110df951'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY = "legacy@semsaviour.invalid"
RLS_ROLE = "semsaviour_rls"  # app.database.session.RLS_ROLE
# Tables with a workspace_id whose rows only members may touch, and personal tables (also only their owner).
WORKSPACE_TABLES = ["courses", "documents", "document_chunks", "lessons", "research_jobs", "jobs", "questions"]
PERSONAL_TABLES = ["tutor_sessions", "quizzes", "topic_progress"]
CHILD_TABLES = {"tutor_messages": ("session_id", "tutor_sessions"), "quiz_attempts": ("quiz_id", "quizzes"),
                "attempt_answers": ("attempt_id", "quiz_attempts")}
# (table, column, ondelete, NOT NULL after the backfill)
OWNER_COLUMNS = [
    ("courses", "created_by", "SET NULL", False), ("documents", "uploaded_by", "SET NULL", False),
    ("jobs", "user_id", "SET NULL", False), ("lessons", "owner_id", "SET NULL", False),
    ("lesson_feedback", "user_id", "CASCADE", True), ("quizzes", "user_id", "CASCADE", True),
    ("topic_progress", "user_id", "CASCADE", True), ("tutor_sessions", "user_id", "CASCADE", True),
]


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=200), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('avatar_key', sa.String(length=200), nullable=True),
    sa.Column('preferred_language', sa.String(length=50), nullable=False),
    sa.Column('academic_level', sa.String(length=100), nullable=False),
    sa.Column('learning_preferences', sa.Text(), nullable=False),
    sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('audit_logs',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('target', sa.String(length=320), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_workspace_id'), 'audit_logs', ['workspace_id'], unique=False)
    op.create_table('email_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('purpose', sa.String(length=10), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_email_tokens_user_id'), 'email_tokens', ['user_id'], unique=False)
    op.create_table('invitations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('max_uses', sa.Integer(), nullable=True),
    sa.Column('uses', sa.Integer(), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_invitations_workspace_id'), 'invitations', ['workspace_id'], unique=False)
    op.create_table('refresh_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('family_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_refresh_tokens_family_id'), 'refresh_tokens', ['family_id'], unique=False)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)
    op.create_table('workspace_members',
    sa.Column('workspace_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('workspace_id', 'user_id')
    )
    op.create_index(op.f('ix_workspace_members_user_id'), 'workspace_members', ['user_id'], unique=False)
    op.create_index('uq_workspace_members_one_owner', 'workspace_members', ['workspace_id'], unique=True, postgresql_where=sa.text("role = 'owner'"))

    # Owner columns: added nullable, filled for existing rows, then tightened.
    for table, column, _, _ in OWNER_COLUMNS:
        op.add_column(table, sa.Column(column, sa.Uuid(), nullable=True))
    op.add_column('llm_usage', sa.Column('user_id', sa.Uuid(), nullable=True))
    op.add_column('lessons', sa.Column('visibility', sa.String(length=10), server_default='workspace', nullable=False))
    op.alter_column('lessons', 'visibility', server_default=None)

    # D29: everything that exists already belongs to a placeholder until someone claims it.
    op.execute(f"""
        INSERT INTO users (id, email, password_hash, display_name, preferred_language, academic_level, learning_preferences)
        SELECT gen_random_uuid(), '{LEGACY}', '!', 'Existing data (unclaimed)', 'English', '', ''
        WHERE EXISTS (SELECT 1 FROM workspaces)""")
    legacy = f"(SELECT id FROM users WHERE email = '{LEGACY}')"
    op.execute(f"INSERT INTO workspace_members (workspace_id, user_id, role) SELECT id, {legacy}, 'owner' FROM workspaces")
    for table, column, _, _ in OWNER_COLUMNS:
        if table != "jobs":
            op.execute(f"UPDATE {table} SET {column} = {legacy}")

    for table, column, ondelete, required in OWNER_COLUMNS:
        if required:
            op.alter_column(table, column, nullable=False)
        op.create_foreign_key(f"fk_{table}_{column}", table, 'users', [column], ['id'], ondelete=ondelete)
    op.create_index(op.f('ix_llm_usage_user_id'), 'llm_usage', ['user_id'], unique=False)
    op.create_index(op.f('ix_quizzes_user_id'), 'quizzes', ['user_id'], unique=False)
    op.create_index(op.f('ix_tutor_sessions_user_id'), 'tutor_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_lessons_owner_id'), 'lessons', ['owner_id'], unique=False)

    # Lessons: one shared per topic and depth, one private per person (D28).
    op.drop_constraint('uq_lessons_topic_depth', 'lessons', type_='unique')
    op.create_index('uq_lessons_private', 'lessons', ['topic_id', 'depth', 'owner_id'], unique=True, postgresql_where=sa.text("visibility = 'private'"))
    op.create_index('uq_lessons_shared', 'lessons', ['topic_id', 'depth'], unique=True, postgresql_where=sa.text("visibility = 'workspace'"))

    # Progress is per person: key (user, topic).
    op.drop_constraint('topic_progress_pkey', 'topic_progress', type_='primary')
    op.create_primary_key('topic_progress_pkey', 'topic_progress', ['user_id', 'topic_id'])
    op.create_index(op.f('ix_topic_progress_topic_id'), 'topic_progress', ['topic_id'], unique=False)

    # Row-level security (D27). API transactions run as RLS_ROLE with app.user_id set (database.session); a
    # superuser or the table owner without app.user_id (workers, migrations, scripts) is the system: allowed.
    op.execute(f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{RLS_ROLE}') THEN CREATE ROLE {RLS_ROLE} NOLOGIN; END IF;
        END $$;
        GRANT {RLS_ROLE} TO CURRENT_USER;
        GRANT USAGE ON SCHEMA public TO {RLS_ROLE};
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {RLS_ROLE};
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {RLS_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {RLS_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {RLS_ROLE};

        CREATE FUNCTION app_user() RETURNS uuid LANGUAGE sql STABLE
            AS $f$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $f$;
        CREATE FUNCTION app_member(ws uuid) RETURNS boolean LANGUAGE sql STABLE AS $f$
            SELECT app_user() IS NULL
                OR EXISTS (SELECT 1 FROM workspace_members m WHERE m.workspace_id = ws AND m.user_id = app_user())
        $f$;
    """)
    for table in WORKSPACE_TABLES + PERSONAL_TABLES + list(CHILD_TABLES):
        if table in CHILD_TABLES:
            column, parent = CHILD_TABLES[table]
            rule = f"app_user() IS NULL OR {column} IN (SELECT id FROM {parent})"  # the parent's policy filters it
        elif table in PERSONAL_TABLES:
            rule = "app_member(workspace_id) AND (app_user() IS NULL OR user_id = app_user())"
        else:
            rule = "app_member(workspace_id)"
        op.execute(f"""
            ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
            ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
            CREATE POLICY tenant_isolation ON {table} USING ({rule}) WITH CHECK ({rule});
        """)


def downgrade() -> None:
    for table in WORKSPACE_TABLES + PERSONAL_TABLES + list(CHILD_TABLES):
        op.execute(f"DROP POLICY tenant_isolation ON {table}; ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY; "
                   f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP FUNCTION app_member(uuid); DROP FUNCTION app_user();")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {RLS_ROLE}; "
               f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {RLS_ROLE}; "
               f"REVOKE USAGE ON SCHEMA public FROM {RLS_ROLE}; "
               f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {RLS_ROLE}; "
               f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {RLS_ROLE};")

    op.drop_index(op.f('ix_topic_progress_topic_id'), table_name='topic_progress')
    op.drop_constraint('topic_progress_pkey', 'topic_progress', type_='primary')
    # Single-user progress keeps one row per topic: the earliest-updated duplicates go.
    op.execute("DELETE FROM topic_progress a USING topic_progress b WHERE a.topic_id = b.topic_id AND a.ctid < b.ctid")
    op.create_primary_key('topic_progress_pkey', 'topic_progress', ['topic_id'])

    op.drop_index('uq_lessons_shared', table_name='lessons', postgresql_where=sa.text("visibility = 'workspace'"))
    op.drop_index('uq_lessons_private', table_name='lessons', postgresql_where=sa.text("visibility = 'private'"))
    op.execute("DELETE FROM lessons WHERE visibility = 'private'")
    op.create_unique_constraint('uq_lessons_topic_depth', 'lessons', ['topic_id', 'depth'])

    op.drop_index(op.f('ix_lessons_owner_id'), table_name='lessons')
    op.drop_index(op.f('ix_tutor_sessions_user_id'), table_name='tutor_sessions')
    op.drop_index(op.f('ix_quizzes_user_id'), table_name='quizzes')
    op.drop_index(op.f('ix_llm_usage_user_id'), table_name='llm_usage')
    for table, column, _, _ in OWNER_COLUMNS:
        op.drop_constraint(f"fk_{table}_{column}", table, type_='foreignkey')
        op.drop_column(table, column)
    op.drop_column('lessons', 'visibility')
    op.drop_column('llm_usage', 'user_id')

    op.drop_index('uq_workspace_members_one_owner', table_name='workspace_members', postgresql_where=sa.text("role = 'owner'"))
    op.drop_index(op.f('ix_workspace_members_user_id'), table_name='workspace_members')
    op.drop_table('workspace_members')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_family_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index(op.f('ix_invitations_workspace_id'), table_name='invitations')
    op.drop_table('invitations')
    op.drop_index(op.f('ix_email_tokens_user_id'), table_name='email_tokens')
    op.drop_table('email_tokens')
    op.drop_index(op.f('ix_audit_logs_workspace_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_table('users')
