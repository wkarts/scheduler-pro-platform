from alembic import op

revision = "tenant_0006_appointment_confirmation"
down_revision = "tenant_0005_password_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic cria alembic_version.version_num como VARCHAR(32) por padrão.
    # Esta revisão é deliberadamente descritiva e ultrapassa 32 caracteres.
    # Amplie a coluna ANTES de o Alembic tentar gravar o novo revision id ao
    # finalizar esta migration. PostgreSQL executa o ALTER na mesma transação,
    # portanto uma execução que tenha falhado no version update pode ser
    # repetida com segurança: o DDL anterior foi revertido junto da transação.
    op.execute(
        "alter table alembic_version "
        "alter column version_num type varchar(128)"
    )

    op.execute(
        """
        create table if not exists appointment_confirmation_requests (
          id uuid primary key default uuid_generate_v4(),
          appointment_id uuid not null unique references appointments(id) on delete cascade,
          token_hash varchar(64) not null unique,
          token_ref text not null,
          state varchar(32) not null default 'PENDING',
          confirmation_deadline timestamptz not null,
          expires_at timestamptz not null,
          response varchar(32),
          responded_at timestamptz,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          constraint ck_confirmation_request_state
            check (state in ('PENDING','CONFIRMED','CANCELLED','EXPIRED','REVOKED')),
          constraint ck_confirmation_request_response
            check (response is null or response in ('CONFIRMED','CANCELLED','EXPIRED'))
        )
        """
    )
    op.execute(
        "create index if not exists ix_confirmation_requests_deadline "
        "on appointment_confirmation_requests(state, confirmation_deadline)"
    )
    op.execute(
        "create index if not exists ix_confirmation_requests_expires "
        "on appointment_confirmation_requests(expires_at)"
    )
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
        create table if not exists web_push_vapid_keys (
          singleton smallint primary key default 1,
          public_key text not null,
          private_key_ref text not null,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          constraint ck_web_push_vapid_singleton check (singleton = 1)
        )
        """
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
    op.execute(
        """
        insert into notification_templates(key, channel, body, active) values
          ('appointment_confirmation_request', 'whatsapp',
           'Olá, {{customer_name}}! Seu atendimento de {{service_name}} com {{professional_name}} está reservado para {{starts_at_br}}. Confirme ou cancele pelo link: {{confirmation_url}}', true),
          ('tenant_confirmation_confirmed', 'whatsapp',
           '✅ {{customer_name}} confirmou o agendamento de {{service_name}} para {{starts_at_br}}.', true),
          ('tenant_confirmation_cancelled', 'whatsapp',
           '❌ {{customer_name}} cancelou o agendamento de {{service_name}} para {{starts_at_br}}. O horário foi liberado.', true),
          ('tenant_confirmation_expired', 'whatsapp',
           '⏱️ {{customer_name}} não confirmou o agendamento de {{service_name}} para {{starts_at_br}} dentro do prazo. O horário foi liberado.', true)
        on conflict (key) do update
        set channel=excluded.channel, body=excluded.body, active=excluded.active
        """
    )


def downgrade() -> None:
    op.execute("drop table if exists web_push_subscriptions cascade")
    op.execute("drop table if exists web_push_vapid_keys cascade")
    op.execute("drop table if exists tenant_realtime_events cascade")
    op.execute("delete from notification_templates where key in ('appointment_confirmation_request','tenant_confirmation_confirmed','tenant_confirmation_cancelled','tenant_confirmation_expired')")
    op.execute("drop table if exists appointment_confirmation_requests cascade")
    # Não reduzimos alembic_version para VARCHAR(32): durante downgrade o valor
    # atual ainda é a revisão longa e o próprio Alembic só grava a revisão
    # anterior depois que downgrade() termina. Manter 128 também permite revisões
    # descritivas futuras sem repetir este incidente.
