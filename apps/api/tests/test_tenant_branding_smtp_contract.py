from pathlib import Path

from app.api.v1.routes.health import TENANT_MIGRATION_HEAD
from app.services.notification_service import DEFAULT_TEMPLATES, NotificationService
from app.services.tenant_mail_service import TenantSmtpConfig

ROOT = Path(__file__).resolve().parents[1]


def test_tenant_schema_head_includes_smtp_configuration() -> None:
    assert TENANT_MIGRATION_HEAD == "tenant_0008_mail_mode"
    smtp_migration = (
        ROOT
        / "migrations"
        / "alembic_tenant"
        / "versions"
        / "0007_tenant_smtp.py"
    ).read_text(encoding="utf-8")
    delivery_mode_migration = (
        ROOT
        / "migrations"
        / "alembic_tenant"
        / "versions"
        / "0008_mail_delivery_mode.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "tenant_0007_smtp"' in smtp_migration
    assert "create table if not exists tenant_smtp_settings" in smtp_migration
    assert "appointment_confirmation_request_email" in smtp_migration
    assert 'revision = "tenant_0008_mail_mode"' in delivery_mode_migration
    assert 'down_revision = "tenant_0007_smtp"' in delivery_mode_migration
    assert "delivery_mode" in delivery_mode_migration
    assert "platform" in delivery_mode_migration


def test_smtp_config_requires_connection_and_sender() -> None:
    config = TenantSmtpConfig(
        enabled=True,
        host="smtp.example.com",
        port=587,
        username="user@example.com",
        password_ref="secret://sealed/example",
        from_email="agenda@example.com",
        from_name="Agenda",
        reply_to="",
        use_tls=True,
        use_ssl=False,
        timeout_seconds=15,
    )
    assert config.configured is True


def test_reschedule_template_keeps_confirmation_link_for_whatsapp_and_email() -> None:
    template = DEFAULT_TEMPLATES["appointment_rescheduled"]
    assert "{{confirmation_url}}" in template
    subject = NotificationService.email_subject(
        "appointment_rescheduled_email",
        {"service_name": "Consulta"},
    )
    assert "reagendado" in subject.lower()
    assert "Consulta" in subject


def test_branding_upload_is_limited_and_publicly_renderable() -> None:
    route = (ROOT / "app" / "api" / "v1" / "routes" / "branding.py").read_text(
        encoding="utf-8"
    )
    assert "BRAND_ASSET_MAX_BYTES = 4 * 1024 * 1024" in route
    assert '@router.post("/assets/{kind}")' in route
    assert '@router.get("/assets/{kind}")' in route


def test_runtime_images_receive_release_and_build_metadata() -> None:
    api_dockerfile = (
        ROOT.parents[1] / "infrastructure" / "docker" / "api" / "Dockerfile"
    ).read_text(encoding="utf-8")
    assert "ARG APP_RELEASE_TAG=" in api_dockerfile
    assert "ARG APP_BUILD_SHA=" in api_dockerfile
