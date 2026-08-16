from alembic import op

revision = "tenant_0004_observability_logs"
down_revision = "tenant_0003_scheduler_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists tenant_log_entries (
          id uuid primary key default uuid_generate_v4(),
          source varchar(80) not null,
          service varchar(120) not null,
          level varchar(20) not null default 'INFO',
          event varchar(160) not null,
          message text not null,
          correlation_id varchar(120),
          request_id varchar(120),
          actor varchar(180),
          integration varchar(80),
          error_code varchar(120),
          details jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index if not exists ix_tenant_log_entries_created on tenant_log_entries(created_at desc)")
    op.execute("create index if not exists ix_tenant_log_entries_source_level on tenant_log_entries(source, level, created_at desc)")
    op.execute("create index if not exists ix_tenant_log_entries_integration on tenant_log_entries(integration, created_at desc)")


def downgrade() -> None:
    op.execute("drop table if exists tenant_log_entries cascade")
