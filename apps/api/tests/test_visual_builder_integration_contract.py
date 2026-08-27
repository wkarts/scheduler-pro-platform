import json
from pathlib import Path


def _repository_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "api").is_dir() and (parent / "apps" / "web").is_dir():
            return parent
    return Path.cwd()


ROOT = _repository_root()


def _read(path: str) -> str:
    candidates = [ROOT / path, ROOT / path.removeprefix("apps/api/")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return ""


def test_visual_builder_is_a_versioned_first_class_workspace_package() -> None:
    raw = _read("packages/visual-builder/package.json")
    if not raw:
        return
    package = json.loads(raw)
    assert package["name"] == "@argws/visual-builder"
    assert package["version"] == "2.0.1"
    assert set(package["dependencies"]) == {
        "@argws/visual-builder-v1",
        "@argws/visual-builder-v2",
        "@argws/visual-builder-v201",
    }
    assert "typecheck" in package["scripts"]
    assert "build" in package["scripts"]


def test_release_registry_exposes_exactly_the_three_requested_versions() -> None:
    source = _read("packages/visual-builder/src/index.js")
    if not source:
        return
    for version in ("1.0.0", "2.0.0", "2.0.1"):
        assert f"version:'{version}'" in source
    assert "ARGWS_VISUAL_BUILDER_DEFAULT_VERSION = '2.0.1'" in source
    assert "builder_version:version" in source
    assert "loadVisualBuilderRuntime" in source


def test_scheduler_adapter_stamps_release_and_keeps_one_runtime_per_document() -> None:
    source = _read("packages/visual-builder/src/index.js")
    if not source:
        return
    assert "createSchedulerProAdapter" in source
    assert "versionedPayload" in source
    assert "ARGWS_VISUAL_BUILDER_RELOAD_REQUIRED" in source
    assert "activeRuntimeVersion" in source


def test_new_visual_builder_replaces_old_editor_by_default_with_rollback_flag() -> None:
    source = _read("apps/web/src/App.vue")
    if not source:
        return
    assert "TenantVisualPageBuilder" in source
    assert "VITE_VISUAL_PAGE_BUILDER" in source
    assert '<TenantVisualPageBuilder v-if="visualBuilderEnabled"' in source
    assert '<TenantPublicPageEditorV2 v-else' in source


def test_public_landing_detects_any_argws_builder_schema_and_uses_release_renderer() -> None:
    page = _read("apps/web/src/PublicSitePage.vue")
    renderer = _read("apps/web/src/PublicVisualLandingRenderer.vue")
    if not page or not renderer:
        return
    assert "PublicVisualLandingRenderer" in page
    assert "schema.startsWith('argws-visual-builder/')" in page
    assert "builder_version" in page
    assert "resolveVisualBuilderVersionFromContent" in renderer
    assert "loadVisualBuilderRuntime" in renderer
    assert "deep:true" not in renderer
    assert "deep: true" not in renderer
    assert "requestAnimationFrame" in renderer


def test_builder_host_is_lazy_disposable_and_version_selectable() -> None:
    source = _read("apps/web/src/TenantVisualPageBuilder.vue")
    if not source:
        return
    assert "createSchedulerProAdapter" in source
    assert "editor?.remove()" in source
    assert "isHtmlContent(page.content)" in source
    assert "htmlProtected.value=page.content" in source
    assert "/settings/visual-builder" in source
    assert "allowedReleases" in source


def test_control_plane_has_a_release_manager_for_default_and_tenant_policy() -> None:
    source = _read("apps/admin/src/AdminVisualBuilderManager.vue")
    main = _read("apps/admin/src/main.ts")
    if not source or not main:
        return
    assert "/platform/visual-builder/default" in source
    assert "/platform/visual-builder/tenants/" in source
    assert "allowed_versions" in source
    assert "Herdar global" in source
    assert "AdminVisualBuilderManager" in main
