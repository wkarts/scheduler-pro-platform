"""Modelos padrão para reenvio e renovação da confirmação.

Revision ID: tenant_0012_confirmation_resend
Revises: tenant_0011_experience_v2
"""

from alembic import op

revision = "tenant_0012_confirmation_resend"
down_revision = "tenant_0011_experience_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migração somente de dados. Não altera estrutura de tabelas e não sobrescreve
    # personalizações que eventualmente já existam com estas chaves.
    op.execute(
        """
        insert into notification_templates(key, channel, body, active) values
          (
            'appointment_confirmation_resend',
            'whatsapp',
            'Olá, {{customer_name}}! Reenviamos seu link de confirmação para o atendimento de {{starts_at_br}} com {{professional_name}}. Confirme ou cancele aqui: {{confirmation_url}}',
            true
          ),
          (
            'appointment_confirmation_resend_email',
            'email',
            'Olá, {{customer_name}}! Reenviamos seu link de confirmação para o atendimento de {{starts_at_br}} com {{professional_name}}. Confirme ou cancele aqui: {{confirmation_url}}',
            true
          ),
          (
            'appointment_confirmation_renewed',
            'whatsapp',
            'Olá, {{customer_name}}! Geramos um novo prazo para confirmar seu atendimento de {{starts_at_br}} com {{professional_name}}. Confirme ou cancele pelo novo link: {{confirmation_url}}',
            true
          ),
          (
            'appointment_confirmation_renewed_email',
            'email',
            'Olá, {{customer_name}}! Geramos um novo prazo para confirmar seu atendimento de {{starts_at_br}} com {{professional_name}}. Confirme ou cancele pelo novo link: {{confirmation_url}}',
            true
          )
        on conflict (key) do nothing
        """
    )


def downgrade() -> None:
    op.execute(
        """
        delete from notification_templates
        where key in (
          'appointment_confirmation_resend',
          'appointment_confirmation_resend_email',
          'appointment_confirmation_renewed',
          'appointment_confirmation_renewed_email'
        )
        """
    )
