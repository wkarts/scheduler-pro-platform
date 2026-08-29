from pathlib import Path

from app.api.v1.routes.pwa_identity import (
    CORE_PWA_NAME,
    TENANT_PWA_ICONS,
    _allow_tenant_pwa_icon,
    _allow_tenant_pwa_name,
)


def _root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "web").is_dir() and (parent / "apps" / "admin").is_dir():
            return parent
    return None


def _read(path: str) -> str:
    root = _root()
    if root is None:
        import pytest

        pytest.skip("Fontes do monorepo não estão presentes nesta imagem.")
    return (root / path).read_text(encoding="utf-8")


def test_tenant_pwa_name_and_icon_overrides_are_independent_and_opt_in() -> None:
    assert CORE_PWA_NAME == "Scheduler Pro"
    assert _allow_tenant_pwa_name({}) is False
    assert _allow_tenant_pwa_icon({}) is False
    assert _allow_tenant_pwa_name({"settings": {}}) is False
    assert _allow_tenant_pwa_icon({"settings": {}}) is False

    icon_only = {"settings": {"allow_pwa_icon_override": True}}
    assert _allow_tenant_pwa_icon(icon_only) is True
    assert _allow_tenant_pwa_name(icon_only) is False

    name_only = {"settings": {"allow_pwa_name_override": True}}
    assert _allow_tenant_pwa_name(name_only) is True
    assert _allow_tenant_pwa_icon(name_only) is False

    legacy = {"settings": {"allow_pwa_identity_override": True}}
    assert _allow_tenant_pwa_name(legacy) is True
    assert _allow_tenant_pwa_icon(legacy) is True

    explicit_split = {
        "settings": {
            "allow_pwa_identity_override": True,
            "allow_pwa_name_override": False,
            "allow_pwa_icon_override": True,
        }
    }
    assert _allow_tenant_pwa_name(explicit_split) is False
    assert _allow_tenant_pwa_icon(explicit_split) is True


def test_tenant_default_pwa_icon_is_dark_and_distinct_from_control_plane() -> None:
    root = _root()
    if root is None:
        import pytest

        pytest.skip("Fontes do monorepo não estão presentes nesta imagem.")

    tenant_192 = root / "apps/web/public/icons/tenant-pwa-192.png"
    tenant_512 = root / "apps/web/public/icons/tenant-pwa-512.png"
    admin_192 = root / "apps/admin/public/icons/icon-192.png"
    admin_512 = root / "apps/admin/public/icons/icon-512.png"

    assert any("/icons/tenant-pwa-192.png" in icon["src"] for icon in TENANT_PWA_ICONS)
    assert any("/icons/tenant-pwa-512.png" in icon["src"] for icon in TENANT_PWA_ICONS)
    assert tenant_192.is_file()
    assert tenant_512.is_file()
    assert admin_192.is_file()
    assert admin_512.is_file()
    assert tenant_192.read_bytes() != admin_192.read_bytes()
    assert tenant_512.read_bytes() != admin_512.read_bytes()

    admin_manifest = _read("apps/admin/public/manifest.webmanifest")
    assert '"src": "/icons/icon-192.png?v=avb240-brand-v3"' in admin_manifest
    assert '"src": "/icons/icon-512.png?v=avb240-brand-v3"' in admin_manifest
    assert "tenant-pwa-192.png" not in admin_manifest
    assert "tenant-pwa-512.png" not in admin_manifest


def test_web_uses_protected_dynamic_pwa_manifest_with_split_permissions() -> None:
    index = _read("apps/web/index.html")
    route = _read("apps/api/app/api/v1/routes/pwa_identity.py")
    router = _read("apps/api/app/api/v1/router.py")
    assert '/api/v1/pwa/manifest.webmanifest' in index
    assert 'allow_pwa_name_override' in route
    assert 'allow_pwa_icon_override' in route
    assert 'icons = _tenant_icons(manifest) if allow_icon_override else list(TENANT_PWA_ICONS)' in route
    assert 'X-Scheduler-PWA-Identity' in route
    assert 'pwa_identity.router, prefix="/pwa"' in router
    assert 'pwa_identity.router,\n    prefix="/branding"' in router


def test_tenant_shell_uses_runtime_version_endpoint_inside_vue_without_dom_observer() -> None:
    root = _root()
    if root is None:
        import pytest

        pytest.skip("Fontes do monorepo não estão presentes nesta imagem.")
    component = _read("apps/web/src/TenantRuntimeVersion.vue")
    app = _read("apps/web/src/App.vue")
    web_main = _read("apps/web/src/main.ts")
    admin_badge = _read("apps/admin/src/version-badge.ts")

    assert "fetch('/api/v1/version'" in component
    assert "fetch('/api/v1/version'" in admin_badge
    assert 'release_tag' in component
    assert 'build_sha' in component
    assert 'slice(0,8)' in component
    assert '<TenantRuntimeVersion/>' in app
    assert "to=\".tenant-console .sidebar-footer\"" in component
    assert 'MutationObserver' not in component
    assert 'innerHTML' not in component
    assert 'installTenantVersionBadge' not in web_main
    assert not (root / "apps/web/src/tenant-version-badge.ts").exists()
    assert "createApp(App).use(createPinia()).mount('#app')" in web_main


def test_global_branding_does_not_rename_native_application() -> None:
    branding = _read("apps/web/src/branding.ts")
    assert "document.title = 'Scheduler Pro'" in branding
    assert "document.title = manifest.app.public_name" not in branding


def test_control_plane_exposes_independent_pwa_name_and_icon_permissions() -> None:
    component = _read("apps/admin/src/AdminPwaIdentityControl.vue")
    admin_main = _read("apps/admin/src/main.ts")
    assert 'allow_pwa_name_override' in component
    assert 'allow_pwa_icon_override' in component
    assert 'Permitir alterar o ícone do PWA' in component
    assert 'Permitir alterar o nome do PWA' in component
    assert 'allow_pwa_identity_override:false' in component
    assert 'createApp(AdminPwaIdentityControl)' in admin_main
