from pathlib import Path

from app.services.builtin_template_package_service import OFFICIAL_TEMPLATE_KEYS, builtin_template_archive
from app.services.html_template_package_service import HtmlTemplatePackageService


def _repository_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "api").is_dir() and (parent / "packages" / "visual-builder").is_dir():
            return parent
    return None


ROOT = _repository_root()


def _source(path: str) -> str:
    if ROOT is None:
        import pytest

        pytest.skip("Fontes do monorepo não fazem parte da imagem isolada da API.")
    return (ROOT / path).read_text(encoding="utf-8")


def test_official_packages_are_experience_v2_and_without_legacy_login() -> None:
    for key in OFFICIAL_TEMPLATE_KEYS:
        report = HtmlTemplatePackageService.validate(builtin_template_archive(key))
        assert report["valid"], {key: report["errors"]}
        assert report["schema"] == "argws-experience-package/v2"
        assert set(report["surfaces"]) == {"landing", "booking"}


def test_visual_builder_html_document_is_not_replaced_by_empty_canvas() -> None:
    source = _source("packages/visual-builder/src/editor.js")
    assert "if(!isHtmlDocument(this._document)&&!this._document.builder.root_ids.length)" in source
    assert ".upb-html-surface-editor iframe,[data-upb-html-document-frame]" in source


def test_tenant_visual_builder_autoloads_and_handles_close_event() -> None:
    source = _source("apps/web/src/TenantVisualPageBuilder.vue")
    assert "await el.load()" in source
    assert "addEventListener('upb-close',closeAdvanced" in source
    assert "scheduler_pro_public_pages_last_surface" in source


def test_public_pages_workspace_recovers_from_same_hash_and_stuck_loading() -> None:
    app = _source("apps/web/src/App.vue")
    assert "publicPagesEpoch" in app
    assert 'document.addEventListener(\'click\',onPublicPagesNavCapture,true)' in app
    assert "window.location.hash==='#visual-builder'" in app
    assert "publicPagesWatchdog" in app
    assert "now-publicPagesLoadingSince>15000" in app
    assert '<TenantVisualPageBuilder :key="publicPagesEpoch"/>' in app


def test_control_plane_importer_accepts_experience_v2() -> None:
    source = _source("apps/admin/src/AdminHtmlTemplateImportOverlay.vue")
    service = _source("apps/api/app/services/html_template_package_service.py")
    assert "argws-experience-package/v2" in source
    assert "ExperienceContractService.parse_archive" in service
    assert "MAX_ARCHIVE_BYTES = 50 * 1024 * 1024" in service


def test_mobile_drawer_is_topmost_versioned_and_tenant_branded() -> None:
    console = _source("apps/web/src/TenantConsole.vue")
    css = _source("apps/web/src/tenant-shell-contract.css")
    branding = _source("apps/web/src/branding.ts")
    assert "Scheduler Pro · v{{ appVersion }}" in console
    assert "z-index: 30000 !important" in css
    assert "mobile-menu-close" in console
    assert "--sp-sidebar-logo-desktop" in branding
    assert "--sp-sidebar-logo-mobile" in branding
    assert "tenantCustomLogo" in branding
    assert ".tenant-console .sidebar .sp-sidebar-logo" in css
    assert "display: none !important" in css
    assert "background-image: var(--sp-sidebar-logo-desktop" in css
    assert "background-image: var(--sp-sidebar-logo-mobile" in css


def test_desktop_sidebar_branding_keeps_tenant_name_and_version_proportional() -> None:
    app = _source("apps/web/src/App.vue")
    desktop = _source("apps/web/src/tenant-shell-desktop-branding-fix.css")
    assert "tenant-shell-desktop-branding-fix.css" in app
    assert "@media (min-width: 901px)" in desktop
    assert "grid-template-columns: 52px minmax(0, 1fr)" in desktop
    assert "font-size: 14px !important" in desktop
    assert "font-size: 10px !important" in desktop
    assert "text-overflow: ellipsis !important" in desktop
