from pathlib import Path

from app.api.v1.routes.pwa_identity import (
    CORE_PWA_ICONS,
    CORE_PWA_NAME,
    _allow_tenant_pwa_identity,
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


def test_tenant_pwa_identity_override_is_opt_in() -> None:
    assert CORE_PWA_NAME == "Scheduler Pro"
    assert _allow_tenant_pwa_identity({}) is False
    assert _allow_tenant_pwa_identity({"settings": {}}) is False
    assert (
        _allow_tenant_pwa_identity(
            {"settings": {"allow_pwa_identity_override": True}}
        )
        is True
    )
    assert any("/icons/icon-192.png" in icon["src"] for icon in CORE_PWA_ICONS)
    assert any("/icons/icon-512.png" in icon["src"] for icon in CORE_PWA_ICONS)


def test_web_uses_protected_dynamic_pwa_manifest() -> None:
    index = _read("apps/web/index.html")
    route = _read("apps/api/app/api/v1/routes/pwa_identity.py")
    assert '/api/v1/pwa/manifest.webmanifest' in index
    assert 'name = CORE_PWA_NAME' in route
    assert 'icons = list(CORE_PWA_ICONS)' in route
    assert 'allow_pwa_identity_override' in route
    assert 'X-Scheduler-PWA-Identity' in route


def test_tenant_shell_uses_runtime_version_endpoint_like_control_plane() -> None:
    tenant_badge = _read("apps/web/src/tenant-version-badge.ts")
    admin_badge = _read("apps/admin/src/version-badge.ts")
    web_main = _read("apps/web/src/main.ts")
    assert "fetch('/api/v1/version'" in tenant_badge
    assert "fetch('/api/v1/version'" in admin_badge
    assert 'release_tag' in tenant_badge
    assert 'build_sha' in tenant_badge
    assert 'slice(0, 8)' in tenant_badge
    assert 'installTenantVersionBadge()' in web_main
    assert "topVersion.style.display = 'none'" in tenant_badge
    assert 'Scheduler Pro · ${status}' in tenant_badge


def test_global_branding_does_not_rename_native_application() -> None:
    branding = _read("apps/web/src/branding.ts")
    assert "document.title = 'Scheduler Pro'" in branding
    assert "document.title = manifest.app.public_name" not in branding


def test_control_plane_exposes_pwa_identity_override_only_as_admin_opt_in() -> None:
    component = _read("apps/admin/src/AdminPwaIdentityControl.vue")
    admin_main = _read("apps/admin/src/main.ts")
    assert 'allow_pwa_identity_override' in component
    assert 'Permitir identidade própria no PWA' in component
    assert 'PWA protegido: nome e ícones permanecem Scheduler Pro.' in component
    assert 'createApp(AdminPwaIdentityControl)' in admin_main
