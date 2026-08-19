from alembic import op

revision = "tenant_0007_smtp"
down_revision = "tenant_0006_appointment_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        create table if not exists tenant_smtp_settings (
          singleton smallint primary key default 1,
          enabled boolean not null default false,
          host varchar(255),
          port integer not null default 587,
          username varchar(320),
          password_ref text,
          from_email varchar(320),
          from_name varchar(200),
          reply_to varchar(320),
          use_tls boolean not null default true,
          use_ssl boolean not null default false,
          timeout_seconds integer not null default 15,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          constraint ck_tenant_smtp_singleton check (singleton = 1),
          constraint ck_tenant_smtp_port check (port between 1 and 65535),
          constraint ck_tenant_smtp_timeout check (timeout_seconds between 1 and 120),
          constraint ck_tenant_smtp_tls_ssl check (not (use_tls and use_ssl))
        )
        """
    )
    op.execute(
        """
        insert into notification_templates(key, channel, body, active) values
          ('appointment_rescheduled', 'whatsapp',
           'Olá, {{customer_name}}! Seu atendimento de {{service_name}} foi reagendado para {{starts_at_br}}. Confirme ou cancele pelo link: {{confirmation_url}}', true),
          ('appointment_confirmation_request_email', 'email',
           'Olá, {{customer_name}}! Seu atendimento de {{service_name}} com {{professional_name}} está reservado para {{starts_at_br}}. Confirme ou cancele pelo link: {{confirmation_url}}', true),
          ('appointment_confirmed_email', 'email',
           'Olá, {{customer_name}}! Seu agendamento de {{service_name}} com {{professional_name}} foi confirmado para {{starts_at_br}}.', true),
          ('appointment_cancelled_email', 'email',
           'Olá, {{customer_name}}. Seu agendamento de {{service_name}} para {{starts_at_br}} foi cancelado. Motivo: {{reason}}', true),
          ('appointment_reminder_24h_email', 'email',
           'Lembrete: {{customer_name}}, seu atendimento de {{service_name}} com {{professional_name}} é amanhã, {{starts_at_br}}.', true),
          ('appointment_reminder_2h_email', 'email',
           'Lembrete: {{customer_name}}, faltam 2 horas para seu atendimento de {{service_name}} com {{professional_name}} às {{starts_at_br}}.', true),
          ('appointment_rescheduled_email', 'email',
           'Olá, {{customer_name}}! Seu atendimento de {{service_name}} foi reagendado para {{starts_at_br}}. Confirme ou cancele pelo link: {{confirmation_url}}', true)
        on conflict (key) do nothing
        """
    )


def downgrade() -> None:
    op.execute(
        "delete from notification_templates where key in ("
        "'appointment_rescheduled',"
        "'appointment_confirmation_request_email',"
        "'appointment_confirmed_email',"
        "'appointment_cancelled_email',"
        "'appointment_reminder_24h_email',"
        "'appointment_reminder_2h_email',"
        "'appointment_rescheduled_email')"
    )
    op.execute("drop table if exists tenant_smtp_settings cascade")
