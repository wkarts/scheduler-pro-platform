from pathlib import Path

import pytest

from app.core.errors import APIError
from app.services.file_service import TenantFileService

ROOT = Path(__file__).resolve().parents[1]


def _repository_root() -> Path:
    """Resolve o monorepo no checkout completo sem quebrar coleta no container API.

    A suíte de integração copia apenas `apps/api` para `/app`; testes marcados como
    não-integração ainda são importados durante a coleta, portanto a descoberta da
    raiz não pode depender de um número fixo de ancestrais.
    """
    for candidate in (ROOT, *ROOT.parents):
        if (candidate / "apps/api").is_dir() and (candidate / "apps/web").is_dir():
            return candidate
    return ROOT


REPO = _repository_root()
WEB = REPO / "apps/web/src"


def test_storage_quota_allows_replacement_without_double_counting() -> None:
    projected = TenantFileService.ensure_within_quota(
        used_bytes=900,
        existing_bytes=400,
        incoming_bytes=450,
        quota_bytes=1000,
    )
    assert projected == 950


def test_storage_quota_rejects_new_file_above_limit() -> None:
    with pytest.raises(APIError) as exc_info:
        TenantFileService.ensure_within_quota(
            used_bytes=900,
            existing_bytes=0,
            incoming_bytes=200,
            quota_bytes=1000,
        )
    assert exc_info.value.code == "STORAGE_QUOTA_EXCEEDED"
    assert exc_info.value.status_code == 413


def test_public_assets_are_limited_to_landing_prefix() -> None:
    public_routes = (ROOT / "app/api/v1/routes/public.py").read_text(encoding="utf-8")
    files_routes = (ROOT / "app/api/v1/routes/files.py").read_text(encoding="utf-8")

    assert '@router.get("/assets/{key:path}")' in public_routes
    assert 'PUBLIC_LANDING_ASSET_PREFIX = "landing/"' in public_routes
    assert 'normalized.startswith(PUBLIC_LANDING_ASSET_PREFIX)' in public_routes
    assert 'f"/api/v1/public/assets/{quote(normalized, safe=\'/\')}"' in files_routes


def test_public_surfaces_are_separated_and_editor_uses_real_renderer() -> None:
    app = (WEB / "App.vue").read_text(encoding="utf-8")
    site = (WEB / "PublicSitePage.vue").read_text(encoding="utf-8")
    editor = (WEB / "TenantPublicPageEditorV2.vue").read_text(encoding="utf-8")
    renderer = (WEB / "PublicLandingRenderer.vue").read_text(encoding="utf-8")

    assert "PublicSitePage" in app
    assert "TenantPublicPageEditorV2" in app
    assert "TenantWorkspaceCoordinator" in app
    assert "from './TenantPublicPageEditor.vue'" not in app
    assert "'/agendar'" in app and "'/pagina'" in app
    assert "landingMode" in site
    assert "PublicLandingRenderer" in editor
    assert ':viewport-override="device"' in editor
    assert "fake-grid" not in editor
    assert "fake-cards" not in editor
    assert "viewportOverride" in renderer
    assert 'data-viewport="viewport"' in renderer
    assert 'data-viewport="mobile"' in renderer


def test_smtp_selector_has_single_flight_guard_and_no_character_data_observer() -> None:
    source = (WEB / "TenantMailModeSelector.vue").read_text(encoding="utf-8")

    assert "if(loading.value)return" in source
    assert "requestGeneration" in source
    assert "requestAnimationFrame" in source
    assert "characterData" not in source
    assert 'to=".tenant-console .main-content > .sp-extension-root"' in source
    assert "position:fixed" not in source


def test_default_tenant_storage_quota_is_two_gib() -> None:
    context = (ROOT / "app/core/tenant_context.py").read_text(encoding="utf-8")
    resolver = (ROOT / "app/services/tenant_resolver.py").read_text(encoding="utf-8")
    management = (ROOT / "app/api/v1/routes/tenant_management.py").read_text(encoding="utf-8")

    assert "DEFAULT_TENANT_STORAGE_QUOTA_BYTES = 2 * 1024 * 1024 * 1024" in context
    assert 'tenant_settings.get("storage_quota_bytes")' in resolver
    assert "storage_quota_mb" in management
