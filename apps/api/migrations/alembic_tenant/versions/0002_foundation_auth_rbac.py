from alembic import op

revision = "tenant_0002"
down_revision = "tenant_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = [
        """create table if not exists users (
            id uuid primary key default uuid_generate_v4(),
            email varchar(180) not null unique,
            password_hash text not null,
            display_name varchar(160) not null,
            is_active boolean not null default true,
            failed_login_attempts integer not null default 0,
            locked_until timestamptz,
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )""",
        """create table if not exists roles (
            id uuid primary key default uuid_generate_v4(),
            name varchar(120) not null unique,
            description text,
            created_at timestamptz not null default now()
        )""",
        """create table if not exists permissions (
            id uuid primary key default uuid_generate_v4(),
            key varchar(160) not null unique,
            description text,
            created_at timestamptz not null default now()
        )""",
        """create table if not exists user_roles (
            user_id uuid not null references users(id) on delete cascade,
            role_id uuid not null references roles(id) on delete cascade,
            primary key(user_id, role_id)
        )""",
        """create table if not exists role_permissions (
            role_id uuid not null references roles(id) on delete cascade,
            permission_id uuid not null references permissions(id) on delete cascade,
            primary key(role_id, permission_id)
        )""",
        """create table if not exists user_sessions (
            id uuid primary key default uuid_generate_v4(),
            user_id uuid not null references users(id) on delete cascade,
            created_at timestamptz not null default now(),
            last_seen_at timestamptz not null default now(),
            expires_at timestamptz not null,
            revoked_at timestamptz,
            user_agent text,
            ip_address varchar(64)
        )""",
        "create index if not exists idx_user_sessions_user on user_sessions(user_id)",
        """create table if not exists refresh_tokens (
            id uuid primary key default uuid_generate_v4(),
            session_id uuid not null references user_sessions(id) on delete cascade,
            user_id uuid not null references users(id) on delete cascade,
            token_hash varchar(64) not null unique,
            expires_at timestamptz not null,
            created_at timestamptz not null default now(),
            revoked_at timestamptz,
            replaced_by_token_id uuid references refresh_tokens(id) on delete set null
        )""",
        "create index if not exists idx_refresh_tokens_session on refresh_tokens(session_id)",
        """create table if not exists password_reset_tokens (
            id uuid primary key default uuid_generate_v4(),
            user_id uuid not null references users(id) on delete cascade,
            token_hash varchar(64) not null unique,
            expires_at timestamptz not null,
            used_at timestamptz,
            created_at timestamptz not null default now()
        )""",
        """create table if not exists audit_logs (
            id uuid primary key default uuid_generate_v4(),
            user_id uuid references users(id) on delete set null,
            action varchar(120) not null,
            result varchar(32) not null,
            ip_address varchar(64),
            correlation_id varchar(120),
            metadata jsonb not null default '{}',
            created_at timestamptz not null default now()
        )""",
        "create index if not exists idx_audit_logs_user on audit_logs(user_id)",
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("drop table if exists audit_logs")
    op.execute("drop table if exists password_reset_tokens")
    op.execute("drop table if exists refresh_tokens")
    op.execute("drop table if exists user_sessions")
    op.execute("drop table if exists role_permissions")
    op.execute("drop table if exists user_roles")
    op.execute("drop table if exists permissions")
    op.execute("drop table if exists roles")
    op.execute("drop table if exists users")
