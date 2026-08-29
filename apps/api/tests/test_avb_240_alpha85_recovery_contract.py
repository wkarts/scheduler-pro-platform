from pathlib import Path

from app.services.builtin_template_package_service import OFFICIAL_TEMPLATE_KEYS, builtin_template_archive
from app.services.html_template_package_service import HtmlTemplatePackageService

ROOT = Path(__file__).resolve().parents[3]


def test_official_packages_are_experience_v2_and_without_legacy_login() -> None:
    for key in OFFICIAL_TEMPLATE_KEYS:
        report = HtmlTemplatePackageService.validate(builtin_template_archive(key))
        assert report["valid"], {key: report["errors"]}
        assert report["schema"] == "argws-experience-package/v2"
        assert set(report["surfaces"]) == {"landing", "booking"}


def test_visual_builder_html_document_is_not_replaced_by_empty_canvas() -> None:
    source = (ROOT / "packages/visual-builder/src/editor.js").read_text(encoding="utf-8")
    assert "if(!isHtmlDocument(this._document)&&!this._document.builder.root_ids.length)" in source
    assert ".upb-html-surface-editor iframe,[data-upb-html-document-frame]" in source


def test_tenant_visual_builder_autoloads_and_handles_close_event() -> None:
    source = (ROOT / "apps/web/src/TenantVisualPageBuilder.vue").read_text(encoding="utf-8")
    assert "await el.load()" in source
    assert "addEventListener('upb-close',closeAdvanced" in source
    assert "scheduler_pro_public_pages_last_surface" in source


def test_control_plane_importer_accepts_experience_v2() -> None:
    source = (ROOT / "apps/admin/src/AdminHtmlTemplateImportOverlay.vue").read_text(encoding="utf-8")
    service = (ROOT / "apps/api/app/services/html_template_package_service.py").read_text(encoding="utf-8")
    assert "argws-experience-package/v2" in source
    assert "ExperienceContractService.parse_archive" in service
    assert "MAX_ARCHIVE_BYTES = 50 * 1024 * 1024" in service


def test_mobile_drawer_is_topmost_and_versioned() -> None:
    console = (ROOT / "apps/web/src/TenantConsole.vue").read_text(encoding="utf-8")
    css = (ROOT / "apps/web/src/tenant-shell-contract.css").read_text(encoding="utf-8")
    assert "Scheduler Pro · v{{ appVersion }}" in console
    assert "z-index: 30000 !important" in css
    assert "mobile-menu-close" in console
