from pathlib import Path

from app.services.tenant_access_resend_service import TenantAccessResendService


def _repository_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "api").is_dir() and (parent / "apps" / "web").is_dir():
            return parent
    # No container de integração apenas apps/api é copiado para /app. Os testes
    # deste módulo não são marcados como integration, mas o pytest importa o
    # módulo durante a coleta. Retornar o cwd evita falha de collection sem
    # mascarar a validação quando o teste roda no checkout completo.
    return Path.cwd()


ROOT = _repository_root()


def test_public_booking_and_admin_access_surfaces_exist() -> None:
    public_site = (ROOT / "apps/web/src/PublicSitePage.vue").read_text(encoding="utf-8")
    public_booking = (ROOT / "apps/web/src/PublicBookingWidget.vue").read_text(encoding="utf-8")
    tenant_drawer = (ROOT / "apps/admin/src/TenantManagementDrawer.vue").read_text(encoding="utf-8")
    admin = (ROOT / "apps/admin/src/AdminControlPlane.vue").read_text(encoding="utf-8")
    assert "PublicBookingWidget" in public_site
    assert "public-booking-workspace" in public_booking
    assert "TenantLogInspector" in tenant_drawer
    assert "Usuários e acessos" in admin


def test_tenant_root_is_admin_without_required_endpoint() -> None:
    app = (ROOT / "apps/web/src/App.vue").read_text(encoding="utf-8")
    assert "['/agendar','/pagina'].includes(normalizedPath)" in app
    assert "const publicRoot=" not in app
    assert "normalizedPath==='/'" not in app
    assert "activeView==='agenda'" in app


def test_admin_access_resend_uses_existing_mail_delivery() -> None:
    source = (
        ROOT / "apps/api/app/services/tenant_access_resend_service.py"
    ).read_text(encoding="utf-8")
    assert "mail_delivery" in source
    assert "send_tenant_welcome" in source
    assert "temporary_password" in source


def test_temporary_password_is_strong_enough() -> None:
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


def test_navigation_is_route_driven_and_pwa_version_handoff_is_installed() -> None:
    main = (ROOT / "apps/web/src/main.ts").read_text(encoding="utf-8")
    console = (ROOT / "apps/web/src/TenantConsole.vue").read_text(encoding="utf-8")
    pwa = (ROOT / "apps/web/src/pwa.ts").read_text(encoding="utf-8")
    sw = (ROOT / "apps/web/public/sw.js").read_text(encoding="utf-8")
    mobile = (ROOT / "apps/mobile/src/navigation-refresh.ts").read_text(encoding="utf-8")
    assert "installTenantNavigationRuntime" not in main
    assert "installTenantExtensionNavigationBridge" not in main
    assert "window.location.hash = key" in console
    assert "TenantWorkspaceCoordinator" not in (ROOT / "apps/web/src/App.vue").read_text(encoding="utf-8")
    assert "controllerchange" in pwa
    assert "registration.update()" in pwa
    assert "const CACHE_PREFIX = 'scheduler-pro-web-'" in sw
    assert "keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE)" in sw
    assert "caches.delete(key)" in sw
    assert "scheduleRefresh" in mobile
