"""Additive individual profiles; existing accounts are not required to reverify."""

from alembic import op

revision = "tenant_0014_identity"
down_revision = "tenant_0013_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in (
        "alter table roles add column if not exists is_active boolean not null default true",
        "alter table users add column if not exists phone varchar(40)",
        "alter table users add column if not exists professional_id uuid references professionals(id) on delete set null",
        "alter table users add column if not exists avatar_key text",
        "alter table users add column if not exists email_verified_at timestamptz",
        "alter table users add column if not exists verification_required boolean not null default false",
        "alter table users add column if not exists last_login_at timestamptz",
        "create unique index if not exists uq_user_professional on users(professional_id) where professional_id is not null",
        "create index if not exists ix_user_email_lookup on users(lower(email))",
        """create table if not exists identity_email_tokens (
            id uuid primary key default uuid_generate_v4(),
            user_id uuid not null references users(id) on delete cascade,
            token_hash varchar(64) not null unique,
            purpose varchar(20) not null check(purpose in ('invite','verify','change')),
            previous_email varchar(180) not null,
            email varchar(180) not null,
            created_at timestamptz not null default now(),
            expires_at timestamptz not null,
            used_at timestamptz
        )""",
        "create index if not exists ix_identity_email_user on identity_email_tokens(user_id,created_at)",
        """insert into permissions(key,description) values
            ('users.read','Consultar usuários e grupos'),
            ('users.manage','Administrar usuários e seus grupos'),
            ('groups.manage','Administrar grupos e permissões'),
            ('users.audit','Consultar histórico de acessos') on conflict(key) do nothing""",
        # Keep existing administrators functional, without changing any existing grants.
        """insert into role_permissions(role_id,permission_id)
            select distinct rp.role_id,p.id from role_permissions rp
            join permissions existing on existing.id=rp.permission_id and existing.key='tenant.manage'
            cross join permissions p where p.key in ('users.read','users.manage','groups.manage','users.audit')
            on conflict do nothing""",
        # Only backfill a known historical login timestamp; do not mark mail as verified.
        """update users u set last_login_at=a.last_login from
            (select user_id,max(created_at) last_login from audit_logs
             where action='auth.login' and result='SUCCESS' group by user_id) a
            where u.id=a.user_id and u.last_login_at is null""",
    ):
        op.execute(statement)


def downgrade() -> None:
    op.execute("drop table if exists identity_email_tokens")
    op.execute("drop index if exists uq_user_professional")
    op.execute("drop index if exists ix_user_email_lookup")
    for column in (
        "phone",
        "professional_id",
        "avatar_key",
        "email_verified_at",
        "verification_required",
        "last_login_at",
    ):
        op.execute(f"alter table users drop column if exists {column}")
    op.execute("alter table roles drop column if exists is_active")
    # Keep permissions and all preexisting users/roles. No account is deleted on rollback.
