from alembic import op

revision = "platform_0005"
down_revision = "platform_0004"
branch_labels = None
depends_on = None

PERMISSIONS = [
    ("platform.dashboard.read", "Visualizar visão geral do Control Plane", "platform"),
    ("platform.users.manage", "Criar, editar, bloquear e excluir usuários administrativos", "identity"),
    ("platform.roles.manage", "Administrar perfis e permissões", "identity"),
    ("platform.tenant_access.manage", "Administrar escopo de tenants dos usuários", "identity"),
    ("tenants.read", "Visualizar tenants", "tenants"),
    ("tenants.create", "Criar tenants", "tenants"),
    ("tenants.update", "Editar tenants", "tenants"),
    ("tenants.provision", "Provisionar e repetir provisionamento", "tenants"),
    ("tenants.delete", "Excluir tenant preservando trilha de auditoria", "tenants"),
    ("tenants.purge", "Expurgar recursos e dados de tenant", "tenants"),
    ("tenant.capabilities.manage", "Liberar ou revogar recursos por tenant", "tenants"),
    ("domains.read", "Visualizar domínios", "domains"),
    ("domains.manage", "Criar e validar DNS/domínios", "domains"),
    ("ssl.manage", "Administrar SSL/ACME", "domains"),
    ("cache.purge", "Executar purge de cache", "domains"),
    ("builds.read", "Visualizar builds e artefatos", "builds"),
    ("builds.manage", "Disparar e sincronizar builds", "builds"),
    ("integrations.read", "Visualizar integrações", "integrations"),
    ("integrations.manage", "Administrar integrações", "integrations"),
    ("observability.read", "Visualizar logs estruturados e console", "observability"),
    ("observability.export", "Exportar logs e evidências", "observability"),
    ("audit.read", "Visualizar auditoria", "audit"),
    ("settings.manage", "Administrar feature flags e parâmetros", "settings"),
    ("branding.manage", "Administrar marca e perfis de distribuição", "branding"),
]

CAPABILITIES = [
    "appointments", "customers", "services", "professionals", "landing_pages",
    "notifications", "automations", "whatsapp", "evolution", "storage",
    "custom_domains", "dns", "ssl", "cloudflare", "branding", "builds",
    "desktop_apps", "android_app", "ios_app", "observability", "audit",
]


def upgrade() -> None:
    op.execute("alter table platform_users add column if not exists display_name varchar(160)")
    op.execute("alter table platform_users add column if not exists must_change_password boolean not null default false")
    op.execute("""create table if not exists platform_permissions (
        key varchar(160) primary key,
        description text not null,
        group_name varchar(80) not null,
        created_at timestamptz not null default now()
    )""")
    op.execute("""create table if not exists platform_roles (
        id uuid primary key default uuid_generate_v4(),
        name varchar(120) not null unique,
        description text,
        is_system boolean not null default false,
        created_at timestamptz not null default now(),
        updated_at timestamptz not null default now()
    )""")
    op.execute("""create table if not exists platform_role_permissions (
        role_id uuid not null references platform_roles(id) on delete cascade,
        permission_key varchar(160) not null references platform_permissions(key) on delete cascade,
        primary key(role_id, permission_key)
    )""")
    op.execute("""create table if not exists platform_user_roles (
        user_id uuid not null references platform_users(id) on delete cascade,
        role_id uuid not null references platform_roles(id) on delete cascade,
        primary key(user_id, role_id)
    )""")
    op.execute("""create table if not exists platform_user_tenants (
        user_id uuid not null references platform_users(id) on delete cascade,
        tenant_id uuid not null references tenants(id) on delete cascade,
        created_at timestamptz not null default now(),
        primary key(user_id, tenant_id)
    )""")
    op.execute("create index if not exists ix_platform_user_tenants_tenant on platform_user_tenants(tenant_id)")
    op.execute("""create table if not exists tenant_capabilities (
        tenant_id uuid not null references tenants(id) on delete cascade,
        capability_key varchar(120) not null,
        enabled boolean not null default false,
        config jsonb not null default '{}'::jsonb,
        updated_at timestamptz not null default now(),
        primary key(tenant_id, capability_key)
    )""")

    for key, description, group_name in PERMISSIONS:
        op.execute(
            "insert into platform_permissions(key, description, group_name) "
            f"values ('{key}', '{description.replace("'", "''")}', '{group_name}') "
            "on conflict(key) do update set description=excluded.description, group_name=excluded.group_name"
        )

    op.execute("""insert into platform_roles(name, description, is_system)
        values
          ('Administrador', 'Administração operacional do Control Plane', true),
          ('Operações', 'Provisionamento, domínios, integrações e builds', true),
          ('Suporte', 'Consulta de tenants, integrações e observabilidade', true),
          ('Auditor', 'Consulta de auditoria e observabilidade', true)
        on conflict(name) do nothing""")

    role_map = {
        "Administrador": [key for key, _, _ in PERMISSIONS if key not in {"tenants.purge"}],
        "Operações": ["platform.dashboard.read", "tenants.read", "tenants.create", "tenants.update", "tenants.provision", "tenant.capabilities.manage", "domains.read", "domains.manage", "ssl.manage", "cache.purge", "builds.read", "builds.manage", "integrations.read", "integrations.manage", "observability.read", "branding.manage"],
        "Suporte": ["platform.dashboard.read", "tenants.read", "domains.read", "builds.read", "integrations.read", "observability.read", "audit.read"],
        "Auditor": ["platform.dashboard.read", "tenants.read", "observability.read", "observability.export", "audit.read"],
    }
    for role, permissions in role_map.items():
        for permission in permissions:
            op.execute(
                "insert into platform_role_permissions(role_id, permission_key) "
                f"select id, '{permission}' from platform_roles where name='{role}' "
                "on conflict do nothing"
            )

    for capability in CAPABILITIES:
        op.execute(
            "insert into tenant_capabilities(tenant_id, capability_key, enabled) "
            f"select id, '{capability}', true from tenants on conflict do nothing"
        )


def downgrade() -> None:
    op.execute("drop table if exists tenant_capabilities")
    op.execute("drop table if exists platform_user_tenants")
    op.execute("drop table if exists platform_user_roles")
    op.execute("drop table if exists platform_role_permissions")
    op.execute("drop table if exists platform_roles")
    op.execute("drop table if exists platform_permissions")
    op.execute("alter table platform_users drop column if exists must_change_password")
    op.execute("alter table platform_users drop column if exists display_name")
