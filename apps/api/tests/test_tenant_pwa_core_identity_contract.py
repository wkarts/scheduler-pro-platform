from pathlib import Path


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


def test_alpha94_pwa_identity_override_is_selectively_removed() -> None:
    index = _read("apps/web/index.html")
    router = _read("apps/api/app/api/v1/router.py")
    admin_main = _read("apps/admin/src/main.ts")
    assert "/api/v1/branding/manifest.webmanifest" in index
    assert "/api/v1/pwa/manifest.webmanifest" not in index
    assert "pwa_identity" not in router
    assert "AdminPwaIdentityControl" not in admin_main


def test_tenant_branding_again_controls_experience_title() -> None:
    branding = _read("apps/web/src/branding.ts")
    assert "document.title = manifest.app.public_name || manifest.app.name" in branding
    assert "document.title = 'Scheduler Pro'" not in branding


def test_tenant_runtime_version_sync_from_alpha94_is_preserved() -> None:
    tenant_badge = _read("apps/web/src/tenant-version-badge.ts")
    admin_badge = _read("apps/admin/src/version-badge.ts")
    web_main = _read("apps/web/src/main.ts")
    assert "fetch('/api/v1/version'" in tenant_badge
    assert "fetch('/api/v1/version'" in admin_badge
    assert "release_tag" in tenant_badge
    assert "build_sha" in tenant_badge
    assert "slice(0, 8)" in tenant_badge
    assert "installTenantVersionBadge()" in web_main
    assert "import './tenant-overlay-layering.css'" in web_main
