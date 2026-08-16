from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def test_scheduler_engine_routes_are_real() -> None:
    appointment_service = (ROOT / "app/services/appointment_service.py").read_text(encoding="utf-8")
    appointment_routes = (ROOT / "app/api/v1/routes/appointments.py").read_text(encoding="utf-8")
    schedule_routes = (ROOT / "app/api/v1/routes/schedule.py").read_text(encoding="utf-8")
    assert "APPOINTMENT_SLOT_UNAVAILABLE" in appointment_service
    assert "blocked_periods" in appointment_service
    assert "business_hours" in appointment_service
    assert '/reschedule")' in appointment_routes
    assert '/confirm")' in appointment_routes
    assert '/check-in")' in appointment_routes
    assert '/complete")' in appointment_routes
    assert 'business-hours' in schedule_routes
    assert 'blocked-periods' in schedule_routes


def test_notification_engine_uses_tenant_templates_reminders_and_dispatcher() -> None:
    notification_service = (ROOT / "app/services/notification_service.py").read_text(encoding="utf-8")
    dispatcher = (ROOT / "app/services/notification_dispatcher.py").read_text(encoding="utf-8")
    tenant_sql = (ROOT / "migrations/tenant/002_scheduler_engine.sql").read_text(encoding="utf-8")
    routes = (ROOT / "app/api/v1/routes/notifications.py").read_text(encoding="utf-8")
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


def test_no_web_auto_login_or_placeholder_modules() -> None:
    app_vue = (REPO / "apps/web/src/App.vue").read_text(encoding="utf-8")
    assert "const logged = ref(!location.pathname" not in app_vue
    assert "localStorage.getItem('scheduler_pro_access_token')" in app_vue
    assert "@submit.prevent=\"login\"" in app_vue
    assert "módulo em evolução" not in app_vue.lower()


def test_desktop_is_remote_webview_and_mobile_is_dedicated() -> None:
    desktop = (REPO / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    admin_desktop = (REPO / "apps/admin-desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    mobile = (REPO / "apps/mobile/src/App.vue").read_text(encoding="utf-8")
    admin_mobile = (REPO / "apps/admin-mobile/src/App.vue").read_text(encoding="utf-8")
    assert '"frontendDist": "https://scheduler.argws.com.br"' in desktop
    assert '"frontendDist": "https://admin.scheduler.argws.com.br"' in admin_desktop
    assert "createAppointment" in mobile and "connectWhatsApp" in mobile
    assert "createTenant" in admin_mobile and "requestBuild" in admin_mobile


def test_cloudpanel_argws_compose_has_bootstrap_workers_and_beat() -> None:
    compose = (REPO / "deployments/cloudpanel/compose.argws.yaml").read_text(encoding="utf-8")
    assert "app.platform_bootstrap" in compose
    assert "scheduler-worker-default" in compose
    assert "scheduler-worker-whatsapp" in compose
    assert "scheduler-beat" in compose
    assert "GITHUB_ACTIONS_TOKEN" in compose
    assert "--without-mingle" in compose
    assert "127.0.0.1" in compose
    assert "18080" in compose
