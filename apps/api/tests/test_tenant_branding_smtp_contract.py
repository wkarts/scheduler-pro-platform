from pathlib import Path

from app.api.v1.routes.health import TENANT_MIGRATION_HEAD
from app.services.notification_service import DEFAULT_TEMPLATES, NotificationService
from app.services.tenant_mail_service import TenantSmtpConfig

ROOT = Path(__file__).resolve().parents[1]


def test_tenant_schema_head_includes_smtp_configuration() -> None:
    assert TENANT_MIGRATION_HEAD == "tenant_0010_phone_guard"
    migration = (
        ROOT
        / "migrations"
        / "alembic_tenant"
        / "versions"
        / "0007_tenant_smtp.py"
    ).read_text(encoding="utf-8")
    open_booking = (
        ROOT
        / "migrations"
        / "alembic_tenant"
        / "versions"
        / "0008_open_booking_and_slot_reuse.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "tenant_0007_smtp"' in migration
    assert "create table if not exists tenant_smtp_settings" in migration
    assert "appointment_confirmation_request_email" in migration
    assert 'revision = "tenant_0008_open_booking"' in open_booking
    assert 'down_revision = "tenant_0007_smtp"' in open_booking


def test_smtp_config_requires_connection_and_sender() -> None:
    config = TenantSmtpConfig(
        enabled=True,
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password_ref="secret://sealed/example",
        from_email="agenda@example.com",
        from_name="Agenda",
        reply_to="agenda@example.com",
        use_tls=True,
        use_ssl=False,
        timeout_seconds=15,
    )
    assert config.is_configured is True


def test_notification_service_keeps_email_templates_and_subjects() -> None:
    assert "appointment_confirmation_request" in DEFAULT_TEMPLATES
    assert "appointment_confirmed" in DEFAULT_TEMPLATES
    assert NotificationService.email_subject(
        "appointment_confirmed",
        {"service_name": "Corte"},
    ).startswith("Agendamento confirmado")
