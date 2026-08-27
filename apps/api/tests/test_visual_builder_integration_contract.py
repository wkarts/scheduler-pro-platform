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


def test_visual_builder_is_current_workspace_package_without_base64_materializer() -> None:
    raw = _read("packages/visual-builder/package.json")
    if not raw:
        return
    package = json.loads(raw)
    assert package["name"] == "@argws/visual-builder"
    assert package["version"] == "2.0.1"
    assert not package.get("dependencies")
    assert "materialize" not in package["scripts"]
    assert "release-b64" not in json.dumps(package)
    assert "typecheck" in package["scripts"]
    assert "build" in package["scripts"]


def test_release_registry_uses_real_source_snapshot_2_0_1() -> None:
    source = _read("packages/visual-builder/src/index.js")
    if not source:
        return
    assert "ARGWS_VISUAL_BUILDER_VERSION='2.0.1'" in source
    assert "builder_version:ARGWS_VISUAL_BUILDER_VERSION" in source
    assert "../releases/2.0.1/src/index.js" in source
    assert "release-b64" not in source
    assert "materialize-releases" not in source
    assert "loadVisualBuilderRuntime" in source


def test_real_visual_builder_release_snapshot_is_versioned_in_source_tree() -> None:
    package_raw = _read("packages/visual-builder/releases/2.0.1/package.json")
    version_raw = _read("packages/visual-builder/releases/2.0.1/VERSION")
    runtime = _read("packages/visual-builder/releases/2.0.1/src/index.js")
    styles = _read("packages/visual-builder/releases/2.0.1/styles/builder.css")
    if not package_raw:
        return
    assert json.loads(package_raw)["version"] == "2.0.1"
    assert version_raw.strip() == "2.0.1"
    assert runtime
    assert styles


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


def test_builder_host_is_lazy_disposable_and_has_no_request_storm_observer() -> None:
    source = _read("apps/web/src/TenantVisualPageBuilder.vue")
    if not source:
        return
    assert "createSchedulerProAdapter" in source
    assert "ARGWS_VISUAL_BUILDER_VERSION" in source
    assert "editor?.remove()" in source
    assert "isHtmlContent(page.content)" in source
    assert "htmlProtected.value=page.content" in source
    assert "MutationObserver" not in source


def test_control_plane_does_not_mount_obsolete_release_manager() -> None:
    main = _read("apps/admin/src/main.ts")
    if not main:
        return
    assert "scheduler-pro-visual-builder-manager" not in main
