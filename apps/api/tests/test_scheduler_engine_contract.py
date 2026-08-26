from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_scheduler_engine_routes_are_real() -> None:
    appointment_service = (ROOT / "app/services/appointment_service.py").read_text(
        encoding="utf-8"
    )
    appointment_routes = (ROOT / "app/api/v1/routes/appointments.py").read_text(
        encoding="utf-8"
    )
    schedule_routes = (ROOT / "app/api/v1/routes/schedule.py").read_text(
        encoding="utf-8"
    )
    assert "APPOINTMENT_SLOT_UNAVAILABLE" in appointment_service
    assert "blocked_periods" in appointment_service
    assert "business_hours" in appointment_service
    assert '/reschedule")' in appointment_routes
    assert '/confirm")' in appointment_routes
    assert '/check-in")' in appointment_routes
    assert '/complete")' in appointment_routes
    assert "business-hours" in schedule_routes
    assert "blocked-periods" in schedule_routes


def test_notification_engine_uses_templates_reminders_and_dispatcher() -> None:
    notification_service = (ROOT / "app/services/notification_service.py").read_text(
        encoding="utf-8"
    )
    dispatcher = (ROOT / "app/services/notification_dispatcher.py").read_text(
        encoding="utf-8"
    )
    tenant_sql = (ROOT / "migrations/tenant/002_scheduler_engine.sql").read_text(
        encoding="utf-8"
    )
    routes = (ROOT / "app/api/v1/routes/notifications.py").read_text(
        encoding="utf-8"
    )
    workers = (ROOT / "app/workers/tasks.py").read_text(encoding="utf-8")
    assert "notification_templates" in notification_service
    assert "appointment_reminder_24h" in notification_service
    assert "appointment_reminder_2h" in notification_service
    assert "{{customer_name}}" in tenant_sql
    assert "ux_notification_jobs_appointment_template" in tenant_sql
    assert "TenantNotificationDispatcher" in dispatcher
    assert "process_all_due_notifications" in workers
    assert '@router.get("/templates")' in routes
    assert '@router.put("/templates/{template_key}")' in routes


def test_product_complete_api_services_exist() -> None:
    provisioning = (ROOT / "app/services/provisioning_runtime.py").read_text(
        encoding="utf-8"
    )
    files = (ROOT / "app/services/file_service.py").read_text(encoding="utf-8")
    github_actions = (ROOT / "app/services/github_actions_service.py").read_text(
        encoding="utf-8"
    )
    secrets = (ROOT / "app/core/secrets.py").read_text(encoding="utf-8")
    migration = (
        ROOT
        / "migrations/alembic_tenant/versions/0004_product_complete.py"
    ).read_text(encoding="utf-8")

    assert "CreateDatabase" in provisioning
    assert "CreateStorage" in provisioning
    assert "CreateAdmin" in provisioning
    assert "FileService" in files
    assert "GITHUB_ACTIONS_TOKEN" in github_actions
    assert "secret://sealed/" in secrets
    assert 'revision = "tenant_0004_product_complete"' in migration


def test_whatsapp_is_tenant_aware() -> None:
    routes = (ROOT / "app/api/v1/routes/whatsapp.py").read_text(encoding="utf-8")
    provider = (ROOT / "app/services/whatsapp_provider.py").read_text(
        encoding="utf-8"
    )
    worker = (ROOT / "app/workers/tasks.py").read_text(encoding="utf-8")

    assert "WhatsAppProviderFactory" in routes
    assert "_tenant_provider" in routes
    assert "whatsapp_integrations" in routes
    assert "get_tenant_context" in routes
    assert "get_tenant_session" in routes
    assert "EvolutionWhatsAppProvider" in provider
    assert "instance_name" in provider
    assert "connect_pairing" in provider
    assert "process_whatsapp_webhook" in worker
