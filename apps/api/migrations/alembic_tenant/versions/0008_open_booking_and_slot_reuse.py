from alembic import op

revision = "tenant_0008_open_booking"
down_revision = "tenant_0007_smtp"
branch_labels = None
depends_on = None


ACTIVE_SLOT_STATUSES = (
    "PENDING",
    "AWAITING_CONFIRMATION",
    "CONFIRMED",
    "CHECKED_IN",
    "IN_PROGRESS",
)


def upgrade() -> None:
    # O schema legado usava UNIQUE(professional_id, starts_at, ends_at), o que
    # mantinha o horário bloqueado mesmo depois de CANCELLED/NO_SHOW/COMPLETED.
    op.execute(
        "alter table appointments "
        "drop constraint if exists uq_appointment_professional_slot"
    )
    op.execute(
        "alter table appointments "
        "drop constraint if exists ex_appointments_professional_active_range"
    )
    op.execute(
        """
        alter table appointments
        add constraint ex_appointments_professional_active_range
        exclude using gist (
          professional_id with =,
          tstzrange(starts_at, ends_at, '[)') with &&
        )
        where (status in (
          'PENDING','AWAITING_CONFIRMATION','CONFIRMED','CHECKED_IN','IN_PROGRESS'
        ))
        """
    )

    # Assunto opcional para e-mails personalizados. WhatsApp ignora este campo.
    op.execute(
        "alter table notification_templates "
        "add column if not exists subject varchar(240)"
    )
    op.execute(
        """
        update notification_templates set subject = case key
          when 'appointment_confirmation_request_email' then 'Confirme seu agendamento'
          when 'appointment_created_email' then 'Recebemos seu agendamento'
          when 'appointment_confirmed_email' then 'Agendamento confirmado'
          when 'appointment_cancelled_email' then 'Agendamento cancelado'
          when 'appointment_rescheduled_email' then 'Seu agendamento foi reagendado'
          when 'appointment_reminder_24h_email' then 'Lembrete do seu agendamento'
          when 'appointment_reminder_2h_email' then 'Seu atendimento está próximo'
          else subject
        end
        where channel='email' and subject is null
        """
    )

    # Evolui somente mensagens ainda iguais aos textos-padrão antigos; templates
    # já personalizados pelo tenant são preservados.
    op.execute(
        """
        update notification_templates
        set body='Olá, {{customer_name}}! 👋\n\nSeu horário para *{{service_name}}* com *{{professional_name}}* foi reservado para *{{starts_at_br}}*.\n\nPara manter o horário, confirme ou cancele pelo link abaixo:\n{{confirmation_url}}\n\nSe precisar alterar, fale com a equipe do estabelecimento.'
        where key='appointment_confirmation_request'
          and channel='whatsapp'
          and body='Olá, {{customer_name}}! Seu atendimento de {{service_name}} com {{professional_name}} está reservado para {{starts_at_br}}. Confirme ou cancele pelo link: {{confirmation_url}}'
        """
    )
    op.execute(
        """
        update notification_templates
        set body='Olá, {{customer_name}}!\n\nSeu agendamento foi *confirmado*. ✅\n\nServiço: {{service_name}}\nProfissional: {{professional_name}}\nData e horário: {{starts_at_br}}\n\nAguardamos você!'
        where key='appointment_confirmed' and channel='whatsapp'
        """
    )
    op.execute(
        """
        update notification_templates
        set body='Olá, {{customer_name}}.\n\nSeu agendamento de {{service_name}} em {{starts_at_br}} foi *cancelado*.\nMotivo: {{reason}}\n\nO horário foi liberado para novos agendamentos.'
        where key='appointment_cancelled' and channel='whatsapp'
        """
    )
    op.execute(
        """
        insert into notification_templates(key, channel, body, active, subject) values
          ('appointment_rescheduled','whatsapp',
           'Olá, {{customer_name}}! 🔄\n\nSeu atendimento de *{{service_name}}* foi reagendado para *{{starts_at_br}}* com *{{professional_name}}*.\n\nConfirme novamente pelo link:\n{{confirmation_url}}', true, null)
        on conflict (key) do nothing
        """
    )


def downgrade() -> None:
    op.execute(
        "alter table appointments "
        "drop constraint if exists ex_appointments_professional_active_range"
    )
    op.execute(
        """
        alter table appointments
        add constraint uq_appointment_professional_slot
        unique (professional_id, starts_at, ends_at)
        """
    )
    op.execute("alter table notification_templates drop column if exists subject")
