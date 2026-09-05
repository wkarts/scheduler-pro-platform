"""Tenant users, reusable groups and private profiles; existing accounts stay usable."""

from alembic import op

revision = "tenant_0014_identity"
down_revision = "tenant_0013_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in (
        "alter table users add column phone varchar(40)",
        "alter table users add column professional_id uuid references professionals(id) on delete set null",
        "create unique index ux_users_professional on users(professional_id) where professional_id is not null",
        "alter table users add column email_verified_at timestamptz",
        # Only newly invited users require verification. No fictitious verification of legacy users.
        "alter table users add column verification_required boolean not null default false",
        "alter table users add column last_login_at timestamptz",
        "alter table users add column avatar_key text",
        "alter table roles add column is_active boolean not null default true",
        "alter table roles add column updated_at timestamptz not null default now()",
        """create table identity_email_tokens (
            id uuid primary key default uuid_generate_v4(),
            user_id uuid not null references users(id) on delete cascade,
            token_hash varchar(64) not null unique,
            purpose varchar(20) not null check(purpose in ('invite','verify','change_email')),
            target_email varchar(180) not null,
            original_email varchar(180) not null,
            expires_at timestamptz not null,
            used_at timestamptz,
            created_at timestamptz not null default now()
        )""",
        "create index ix_identity_email_tokens_user on identity_email_tokens(user_id,created_at desc)",
        "create index ix_identity_audit on audit_logs(created_at desc) where action like 'iam.%'",
        """insert into permissions(key,description) values
            ('users.read','Consultar usuários e grupos'),
            ('users.manage','Administrar contas de usuários'),
            ('groups.manage','Administrar grupos e permissões'),
            ('audit.read','Consultar auditoria de acessos')
            on conflict(key) do nothing""",
        """insert into role_permissions(role_id,permission_id)
            select distinct existing.role_id,newp.id
            from role_permissions existing join permissions p on p.id=existing.permission_id
            cross join permissions newp
            where p.key='tenant.manage'
            and newp.key in ('users.read','users.manage','groups.manage','audit.read')
            on conflict do nothing""",
        """update users u set last_login_at=(
            select max(a.created_at) from audit_logs a
            where a.user_id=u.id and a.action='auth.login' and a.result='SUCCESS')""",
    ):
        op.execute(statement)


def downgrade() -> None:
    op.execute("drop index if exists ix_identity_audit")
    op.execute("drop table identity_email_tokens")
    op.execute("drop index ux_users_professional")
    # Permissions/audit history are retained to avoid destroying a preexisting custom grant.
    for column in (
        "phone",
        "professional_id",
        "email_verified_at",
        "verification_required",
        "last_login_at",
        "avatar_key",
    ):
        op.execute(f"alter table users drop column {column}")
    op.execute("alter table roles drop column is_active, drop column updated_at")
