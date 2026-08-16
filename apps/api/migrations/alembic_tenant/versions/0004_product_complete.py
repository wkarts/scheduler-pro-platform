from alembic import op

revision = "tenant_0004_product_complete"
down_revision = "tenant_0003_scheduler_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists tenant_settings (
          key varchar(120) primary key,
          value jsonb not null default '{}'::jsonb,
          updated_at timestamptz not null default now()
        )
        """
    )
    op.execute("create index if not exists ix_appointment_status_history_appointment_created on appointment_status_history(appointment_id, created_at desc)")
    op.execute("create index if not exists ix_outbox_events_status_created on outbox_events(status, created_at)")


def downgrade() -> None:
    op.execute("drop table if exists tenant_settings cascade")
