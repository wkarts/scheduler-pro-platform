from alembic import op

revision = "platform_0010_admin_2fa"
down_revision = "platform_0009_public_booking"
branch_labels = None
depends_on = None


PERMISSIONS = [
    ("platform.security.manage", "Administrar segurança da plataforma", "security"),
    ("tenant.security.manage", "Administrar segurança da empresa", "tenant-operations"),
    ("tenant.database.manage", "Administrar banco de dados da empresa", "tenant-operations"),
    ("tenant.storage.manage", "Administrar armazenamento da empresa", "tenant-operations"),
    ("tenant.cache.manage", "Administrar cache da empresa", "tenant-operations"),
    ("tenant.processes.manage", "Administrar filas e processamentos da empresa", "tenant-operations"),
    ("tenant.backups.manage", "Administrar backups da empresa", "tenant-operations"),
    ("tenant.backups.restore", "Restaurar backup da empresa", "tenant-operations"),
    ("tenant.logs.read", "Visualizar logs da empresa", "tenant-operations"),
    ("tenant.maintenance.manage", "Executar manutenção da empresa", "tenant-operations"),
]


def _quote(value: str) -> str:
    return value.replace("'", "''")


def upgrade() -> None:
    # 2FA administrativo é obrigatório por política, mas a migration não bloqueia
    # usuários existentes. O primeiro login posterior conduz o administrador ao
    # enrollment e somente depois libera uma sessão administrativa completa.
    op.execute(
        "alter table platform_users add column if not exists "
        "two_factor_enabled boolean not null default false"
    )
    op.execute(
        "alter table platform_users add column if not exists two_factor_secret_ref text"
    )
    op.execute(
        "alter table platform_users add column if not exists two_factor_confirmed_at timestamptz"
    )
    op.execute(
        "alter table platform_users add column if not exists two_factor_updated_at timestamptz"
    )
    op.execute(
        "alter table platform_user_sessions add column if not exists "
        "second_factor_verified boolean not null default false"
    )
    op.execute(
        "alter table platform_user_sessions add column if not exists "
        "second_factor_verified_at timestamptz"
    )

    # Registro independente: continua existindo mesmo quando a conta operacional
    # já foi destruída. Não há FK para tenants de propósito.
    op.execute(
        """
        create table if not exists tenant_purge_audits (
            id uuid primary key default uuid_generate_v4(),
            original_tenant_id uuid not null,
            original_name varchar(160) not null,
            original_slug varchar(120) not null,
            actor_user_id uuid references platform_users(id) on delete set null,
            correlation_id varchar(120) not null,
            status varchar(32) not null default 'PENDING',
            resources_removed jsonb not null default '[]'::jsonb,
            resources_pending jsonb not null default '[]'::jsonb,
            failures jsonb not null default '[]'::jsonb,
            requested_at timestamptz not null default now(),
            completed_at timestamptz,
            unique(original_tenant_id, correlation_id)
        )
        """
    )
    op.execute(
        "create index if not exists ix_tenant_purge_audits_tenant_requested "
        "on tenant_purge_audits(original_tenant_id, requested_at desc)"
    )
    op.execute(
        "create index if not exists ix_tenant_purge_audits_status_requested "
        "on tenant_purge_audits(status, requested_at desc)"
    )

    for key, description, group_name in PERMISSIONS:
        op.execute(
            "insert into platform_permissions(key, description, group_name) "
            f"values ('{key}', '{_quote(description)}', '{group_name}') "
            "on conflict(key) do update set "
            "description=excluded.description, group_name=excluded.group_name"
        )

    # O superadministrador já recebe todas as permissões dinamicamente. Para o
    # papel Administrador, ampliamos apenas operações não destrutivas; purge e
    # restore continuam dependendo de concessão explícita ou superadmin.
    op.execute(
        """
        insert into platform_role_permissions(role_id, permission_key)
        select r.id, p.key
        from platform_roles r
        cross join platform_permissions p
        where r.name='Administrador'
          and p.key in (
            'platform.security.manage',
            'tenant.security.manage',
            'tenant.database.manage',
            'tenant.storage.manage',
            'tenant.cache.manage',
            'tenant.processes.manage',
            'tenant.backups.manage',
            'tenant.logs.read',
            'tenant.maintenance.manage'
          )
        on conflict do nothing
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists tenant_purge_audits")
    op.execute(
        "alter table platform_user_sessions drop column if exists second_factor_verified_at"
    )
    op.execute(
        "alter table platform_user_sessions drop column if exists second_factor_verified"
    )
    op.execute(
        "alter table platform_users drop column if exists two_factor_updated_at"
    )
    op.execute(
        "alter table platform_users drop column if exists two_factor_confirmed_at"
    )
    op.execute(
        "alter table platform_users drop column if exists two_factor_secret_ref"
    )
    op.execute(
        "alter table platform_users drop column if exists two_factor_enabled"
    )
    keys = ",".join(f"'{key}'" for key, _, _ in PERMISSIONS)
    op.execute(f"delete from platform_permissions where key in ({keys})")
