from alembic import op

revision = "tenant_0007_realtime_push"
down_revision = "tenant_0006_appointment_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists tenant_realtime_events (
          sequence bigserial primary key,
          id uuid not null unique default uuid_generate_v4(),
          event_type varchar(120) not null,
          appointment_id uuid references appointments(id) on delete cascade,
          title varchar(220) not null,
          message text not null,
          payload jsonb not null default '{}'::jsonb,
          created_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        "create index if not exists ix_tenant_realtime_events_created "
        "on tenant_realtime_events(created_at desc)"
    )
    op.execute(
        "create index if not exists ix_tenant_realtime_events_appointment "
        "on tenant_realtime_events(appointment_id, sequence desc)"
    )
    op.execute(
        """
        create table if not exists web_push_subscriptions (
          id uuid primary key default uuid_generate_v4(),
          user_id uuid not null references users(id) on delete cascade,
          endpoint text not null unique,
          p256dh text not null,
          auth text not null,
          expiration_time bigint,
          user_agent varchar(500),
          device_label varchar(160),
          active boolean not null default true,
          last_success_at timestamptz,
          last_error text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        )
        """
    )
    op.execute(
        "create index if not exists ix_web_push_subscriptions_user_active "
        "on web_push_subscriptions(user_id, active)"
    )


def downgrade() -> None:
    op.execute("drop table if exists web_push_subscriptions cascade")
    op.execute("drop table if exists tenant_realtime_events cascade")
