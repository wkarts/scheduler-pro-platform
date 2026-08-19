from alembic import op

revision = "platform_0009"
down_revision = "platform_0008"
branch_labels = None
depends_on = None

CAPABILITIES = [
    "appointments",
    "customers",
    "services",
    "professionals",
    "landing_pages",
    "notifications",
    "automations",
    "whatsapp",
    "evolution",
    "storage",
    "custom_domains",
    "dns",
    "ssl",
    "cloudflare",
    "branding",
    "builds",
    "desktop_apps",
    "android_app",
    "ios_app",
    "observability",
    "audit",
]


def _values() -> str:
    return ",".join(f"'{item}'" for item in CAPABILITIES)


def upgrade() -> None:
    values = _values()
    # Não altera contratos existentes. Apenas muda o comportamento de novos
    # tenants: todos os recursos nascem BLOQUEADOS e precisam ser liberados pelo
    # Control Plane. A agenda/recursos contratados podem ser selecionados pelo
    # administrador após a criação ou passados explicitamente no create tenant.
    op.execute(
        f"""
        create or replace function scheduler_seed_tenant_capabilities()
        returns trigger language plpgsql as $$
        begin
          insert into tenant_capabilities(tenant_id, capability_key, enabled)
          select new.id, c.key, false
          from unnest(array[{values}]) as c(key)
          on conflict do nothing;
          return new;
        end;
        $$
        """
    )


def downgrade() -> None:
    values = _values()
    op.execute(
        f"""
        create or replace function scheduler_seed_tenant_capabilities()
        returns trigger language plpgsql as $$
        begin
          insert into tenant_capabilities(tenant_id, capability_key, enabled)
          select new.id, c.key, true
          from unnest(array[{values}]) as c(key)
          on conflict do nothing;
          return new;
        end;
        $$
        """
    )
