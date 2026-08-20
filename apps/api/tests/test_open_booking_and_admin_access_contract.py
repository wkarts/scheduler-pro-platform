from pathlib import Path

from app.services.tenant_access_resend_service import TenantAccessResendService

ROOT = Path(__file__).resolve().parents[3]


def test_cancelled_slots_are_reusable_and_conflicts_are_professional_scoped() -> None:
    migration = (
        ROOT
        / "apps/api/migrations/alembic_tenant/versions/0008_open_booking_and_slot_reuse.py"
    ).read_text(encoding="utf-8")
    assert "drop constraint if exists uq_appointment_professional_slot" in migration
    assert "exclude using gist" in migration
    assert "professional_id with =" in migration
    assert "tstzrange(starts_at, ends_at, '[)') with &&" in migration
    assert "'CANCELLED'" not in migration.split("where (status in (", 1)[1].split("))", 1)[0]


def test_public_booking_is_a_new_isolated_opt_in_module() -> None:
    capability_migration = (
        ROOT
        / "apps/api/migrations/alembic_platform/versions/0009_public_booking_capability.py"
    ).read_text(encoding="utf-8")
    public_routes = (ROOT / "apps/api/app/api/v1/routes/public.py").read_text(encoding="utf-8")
    web = (ROOT / "apps/web/src/TenantBookingAndMessages.vue").read_text(encoding="utf-8")
    assert "'public_booking', false" in capability_migration
    assert "scheduler_seed_public_booking_capability" in capability_migration
    assert 'require_tenant_capability("public_booking")' in public_routes
    assert "capabilities.value.has('public_booking')" in web
    assert "Agenda pública" in web
    assert "HTML complementar" in web


def test_public_booking_and_message_customization_are_exposed() -> None:
    public_routes = (ROOT / "apps/api/app/api/v1/routes/public.py").read_text(encoding="utf-8")
    notification_routes = (ROOT / "apps/api/app/api/v1/routes/notifications.py").read_text(encoding="utf-8")
    notification_service = (ROOT / "apps/api/app/services/notification_service.py").read_text(encoding="utf-8")
    web = (ROOT / "apps/web/src/TenantBookingAndMessages.vue").read_text(encoding="utf-8")
    assert '@router.get("/booking")' in public_routes
    assert '@router.get("/booking/availability")' in public_routes
    assert '@router.post("/booking")' in public_routes
    assert "subject=subject" in notification_routes
    assert "select subject" in notification_service
    assert "Mensagens da agenda" in web


def test_admin_can_resend_access_without_recovering_current_password() -> None:
    route = (ROOT / "apps/api/app/api/v1/routes/tenant_management.py").read_text(encoding="utf-8")
    service = (ROOT / "apps/api/app/services/tenant_access_resend_service.py").read_text(encoding="utf-8")
    drawer = (ROOT / "apps/admin/src/TenantManagementDrawer.vue").read_text(encoding="utf-8")
    assert 'principal-admin/resend-access' in route
    assert "tenant_access_credentials_resent" in service
    assert "generate_temporary_password" in service
    assert "Sua senha atual permanece a mesma" in service
    assert "Salvar e reenviar acesso" in drawer
    assert "Gerar senha temporária e reenviar" in drawer
    password = TenantAccessResendService.generate_temporary_password()
    assert len(password) >= 12


def test_tenant_log_inspector_has_single_scroll_and_progressive_rendering() -> None:
    inspector = (ROOT / "apps/admin/src/TenantLogInspector.vue").read_text(encoding="utf-8")
    drawer = (ROOT / "apps/admin/src/TenantManagementDrawer.vue").read_text(encoding="utf-8")
    assert "visibleCount" in inspector
    assert "Carregar mais" in inspector
    assert ".tenant-log-list{display:grid;gap:8px;min-width:0;overflow:visible}" in inspector
    assert "white-space:pre-wrap" in inspector
    assert "height:100dvh;overflow-y:auto;overflow-x:hidden" in drawer


def test_navigation_refresh_and_pwa_version_handoff_are_installed() -> None:
    web_runtime = (ROOT / "apps/web/src/tenant-navigation-runtime.ts").read_text(encoding="utf-8")
    pwa = (ROOT / "apps/web/src/pwa.ts").read_text(encoding="utf-8")
    sw = (ROOT / "apps/web/public/sw.js").read_text(encoding="utf-8")
    mobile = (ROOT / "apps/mobile/src/navigation-refresh.ts").read_text(encoding="utf-8")
    assert "refreshCurrentView" in web_runtime
    assert "controllerchange" in pwa
    assert "registration.update()" in pwa
    assert "scheduler-pro-web-brand-v3.0.0" in sw
    assert "scheduleRefresh" in mobile
