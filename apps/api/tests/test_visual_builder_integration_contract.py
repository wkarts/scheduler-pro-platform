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


def test_visual_builder_is_single_current_workspace_package() -> None:
    raw = _read("packages/visual-builder/package.json")
    if not raw:
        return
    package = json.loads(raw)
    assert package["name"] == "@argws/visual-builder"
    assert package["version"] == "2.0.1"
    assert not package.get("dependencies")
    assert package["scripts"]["materialize"] == "node scripts/materialize-releases.mjs"
    assert "typecheck" in package["scripts"]
    assert "build" in package["scripts"]


def test_release_registry_exposes_only_2_0_1() -> None:
    source = _read("packages/visual-builder/src/index.js")
    if not source:
        return
    assert "ARGWS_VISUAL_BUILDER_VERSION='2.0.1'" in source
    assert "builder_version:ARGWS_VISUAL_BUILDER_VERSION" in source
    assert "1.0.0" not in source
    assert "2.0.0" not in source
    assert "loadVisualBuilderRuntime" in source


def test_runtime_is_materialized_from_textual_release_and_validated() -> None:
    source = _read("packages/visual-builder/scripts/materialize-releases.mjs")
    if not source:
        return
    assert "const VERSION='2.0.1'" in source
    assert "release-b64" in source
    assert "manifest.version!==VERSION" in source
    assert "gunzipSync" in source


def test_new_visual_builder_replaces_old_editor_by_default_with_rollback_flag() -> None:
    source = _read("apps/web/src/App.vue")
    if not source:
        return
    assert "TenantVisualPageBuilder" in source
    assert "VITE_VISUAL_PAGE_BUILDER" in source
    assert '<TenantVisualPageBuilder v-if="visualBuilderEnabled"' in source
    assert '<TenantPublicPageEditorV2 v-else' in source


def test_public_landing_detects_argws_builder_and_uses_single_runtime() -> None:
    page = _read("apps/web/src/PublicSitePage.vue")
    renderer = _read("apps/web/src/PublicVisualLandingRenderer.vue")
    if not page or not renderer:
        return
    assert "PublicVisualLandingRenderer" in page
    assert "schema.startsWith('argws-visual-builder/')" in page
    assert "builder_version" in page
    assert "loadVisualBuilderRuntime" in renderer
    assert "resolveVisualBuilderVersionFromContent" not in renderer
    assert "deep:true" not in renderer
    assert "deep: true" not in renderer
    assert "requestAnimationFrame" in renderer


def test_builder_host_is_lazy_disposable_and_has_no_version_selector() -> None:
    source = _read("apps/web/src/TenantVisualPageBuilder.vue")
    if not source:
        return
    assert "createSchedulerProAdapter" in source
    assert "ARGWS_VISUAL_BUILDER_VERSION" in source
    assert "editor?.remove()" in source
    assert "isHtmlContent(page.content)" in source
    assert "htmlProtected.value=page.content" in source
    assert "/settings/visual-builder" not in source
    assert "allowedReleases" not in source


def test_control_plane_does_not_mount_obsolete_release_manager() -> None:
    main = _read("apps/admin/src/main.ts")
    if not main:
        return
    assert "AdminVisualBuilderManager" not in main
    assert "scheduler-pro-visual-builder-manager" not in main
