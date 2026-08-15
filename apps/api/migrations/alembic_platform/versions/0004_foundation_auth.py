from alembic import op

revision = "platform_0004"
down_revision = "platform_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        "alter table tenant_databases add column if not exists credential_version integer not null default 1",
        "alter table platform_users add column if not exists is_active boolean not null default true",
        "alter table platform_users add column if not exists failed_login_attempts integer not null default 0",
        "alter table platform_users add column if not exists locked_until timestamptz",
        "alter table platform_users add column if not exists created_at timestamptz not null default now()",
        "alter table platform_users add column if not exists updated_at timestamptz not null default now()",
        """create table if not exists platform_user_sessions (
            id uuid primary key default uuid_generate_v4(),
            user_id uuid not null references platform_users(id) on delete cascade,
            created_at timestamptz not null default now(),
            last_seen_at timestamptz not null default now(),
            expires_at timestamptz not null,
            revoked_at timestamptz,
            user_agent text,
            ip_address varchar(64)
        )""",
        "create index if not exists idx_platform_user_sessions_user on platform_user_sessions(user_id)",
        """create table if not exists platform_refresh_tokens (
            id uuid primary key default uuid_generate_v4(),
            session_id uuid not null references platform_user_sessions(id) on delete cascade,
            user_id uuid not null references platform_users(id) on delete cascade,
            token_hash varchar(64) not null unique,
            expires_at timestamptz not null,
            created_at timestamptz not null default now(),
            revoked_at timestamptz,
            replaced_by_token_id uuid references platform_refresh_tokens(id) on delete set null
        )""",
        "create index if not exists idx_platform_refresh_tokens_session on platform_refresh_tokens(session_id)",
        """create table if not exists platform_audit_logs (
            id uuid primary key default uuid_generate_v4(),
            user_id uuid references platform_users(id) on delete set null,
            action varchar(120) not null,
            result varchar(32) not null,
            ip_address varchar(64),
            correlation_id varchar(120),
            metadata jsonb not null default '{}',
            created_at timestamptz not null default now()
        )""",
        "create index if not exists idx_platform_audit_logs_user on platform_audit_logs(user_id)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("drop table if exists platform_audit_logs")
    op.execute("drop table if exists platform_refresh_tokens")
    op.execute("drop table if exists platform_user_sessions")
    op.execute("alter table platform_users drop column if exists updated_at")
    op.execute("alter table platform_users drop column if exists created_at")
    op.execute("alter table platform_users drop column if exists locked_until")
    op.execute("alter table platform_users drop column if exists failed_login_attempts")
    op.execute("alter table platform_users drop column if exists is_active")
    op.execute("alter table tenant_databases drop column if exists credential_version")
