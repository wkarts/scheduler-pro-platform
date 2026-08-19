from alembic import op

revision = "tenant_0006_appointment_confirmation"
down_revision = "tenant_0005_password_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.execute("delete from notification_templates where key in ('appointment_confirmation_request','tenant_confirmation_confirmed','tenant_confirmation_cancelled','tenant_confirmation_expired')")
    op.execute("drop table if exists appointment_confirmation_requests cascade")
