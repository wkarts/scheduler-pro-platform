from alembic import op

revision = "platform_0005_observability_logs"
down_revision = "platform_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists platform_log_entries (
          id uuid primary key default uuid_generate_v4(),
          tenant_id uuid references tenants(id) on delete set null,
          source varchar(80) not null,
          service varchar(120) not null,
          level varchar(20) not null default 'INFO',
          event varchar(160) not null,
          message text not null,
          correlation_id varchar(120),
          request_id varchar(120),
          actor varchar(180),
          hostname varchar(255),
          container_name varchar(180),
          integration varchar(80),
          error_code varchar(120),
          details jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index if not exists ix_platform_log_entries_created on platform_log_entries(created_at desc)")
    op.execute("create index if not exists ix_platform_log_entries_tenant on platform_log_entries(tenant_id, created_at desc)")
    op.execute("create index if not exists ix_platform_log_entries_source_level on platform_log_entries(source, level, created_at desc)")
    op.execute("create index if not exists ix_platform_log_entries_integration on platform_log_entries(integration, created_at desc)")

    op.execute(
        """
        create table if not exists tenant_resource_boundaries (
          tenant_id uuid primary key references tenants(id) on delete cascade,
          database_name varchar(128) not null,
          database_user varchar(128) not null,
          storage_bucket varchar(160) not null,
          storage_prefix text not null,
          artifact_prefix text not null,
          log_retention_days integer not null default 90,
          isolation_status varchar(32) not null default 'ACTIVE',
          details jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        """
        insert into tenant_resource_boundaries(
          tenant_id, database_name, database_user, storage_bucket, storage_prefix, artifact_prefix, details
        )
        select t.id,
               coalesce(td.database_name, 'tenant_' || replace(t.id::text, '-', '')),
               coalesce(td.database_user, 'tenant_' || replace(t.id::text, '-', '')),
               coalesce(ts.bucket, 'scheduler-tenant-' || t.slug),
               'tenants/' || t.id::text || '/',
               'tenants/' || t.id::text || '/artifacts/',
               jsonb_build_object('slug', t.slug, 'created_from_migration', true)
        from tenants t
        left join tenant_databases td on td.tenant_id=t.id
        left join tenant_storage ts on ts.tenant_id=t.id
        on conflict (tenant_id) do update set
          database_name=excluded.database_name,
          database_user=excluded.database_user,
          storage_bucket=excluded.storage_bucket,
          storage_prefix=excluded.storage_prefix,
          artifact_prefix=excluded.artifact_prefix,
          details=tenant_resource_boundaries.details || excluded.details,
          updated_at=now()
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists tenant_resource_boundaries cascade")
    op.execute("drop table if exists platform_log_entries cascade")
