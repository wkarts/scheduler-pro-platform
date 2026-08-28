import json
from pathlib import Path


def _repository_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "api").is_dir() and (parent / "apps" / "web").is_dir():
            return parent
    return Path.cwd()


ROOT = _repository_root()


def _path(path: str) -> Path:
    candidates = [ROOT / path, ROOT / path.removeprefix("apps/api/")]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _read(path: str) -> str:
    candidate = _path(path)
    return candidate.read_text(encoding="utf-8") if candidate.is_file() else ""


def test_visual_builder_2_1_0_is_the_only_canonical_workspace_release() -> None:
    raw = _read("packages/visual-builder/package.json")
    if not raw:
        return
    package = json.loads(raw)
    assert package["name"] == "@argws/visual-builder"
    assert package["version"] == "2.1.0"
    assert not package.get("dependencies")
    assert "materialize" in package["scripts"]
    assert "release-b64" in json.dumps(package)
    assert "typecheck" in package["scripts"]
    assert "build" in package["scripts"]


def test_release_registry_exposes_only_2_1_0() -> None:
    source = _read("packages/visual-builder/src/index.js")
    if not source:
        return
    assert "ARGWS_VISUAL_BUILDER_VERSION='2.1.0'" in source
    assert "ARGWS_VISUAL_BUILDER_DEFAULT_VERSION='2.1.0'" in source
    assert "Object.freeze(['2.1.0'])" in source
    assert "builder_version:ARGWS_VISUAL_BUILDER_VERSION" in source
    assert "loadVisualBuilderRuntime" in source
    for obsolete in ("1.0.0", "2.0.0", "2.0.1"):
        assert f"releases/{obsolete}" not in source


def test_old_visual_builder_release_directories_are_physically_removed() -> None:
    for obsolete in ("1.0.0", "2.0.0", "2.0.1"):
        assert not _path(f"packages/visual-builder/releases/{obsolete}").exists()
    parts = _path("packages/visual-builder/release-b64/2.1.0")
    assert parts.is_dir()
    assert list(parts.glob("part-*.b64"))
    materializer = _read("packages/visual-builder/scripts/materialize-release.mjs")
    assert "const VERSION = '2.1.0'" in materializer
    assert "EXPECTED_SHA256" in materializer
    assert "template-packages.js" in materializer


def test_scheduler_pro_uses_visual_builder_2_1_0_without_old_editor_fallback() -> None:
    source = _read("apps/web/src/App.vue")
    package = _read("apps/web/package.json")
    if not source or not package:
        return
    assert "TenantVisualPageBuilder" in source
    assert "<TenantVisualPageBuilder/>" in source
    assert "TenantPublicPageEditorV2" not in source
    assert "VITE_VISUAL_PAGE_BUILDER" not in source
    assert json.loads(package)["dependencies"]["@argws/visual-builder"] == "2.1.0"


def test_public_landing_uses_single_canonical_runtime() -> None:
    page = _read("apps/web/src/PublicSitePage.vue")
    renderer = _read("apps/web/src/PublicVisualLandingRenderer.vue")
    if not page or not renderer:
        return
    assert "PublicVisualLandingRenderer" in page
    assert "builder_version" in page
    assert "loadVisualBuilderRuntime" in renderer
    assert "argws-page-renderer" in renderer
    assert "deep:true" not in renderer
    assert "deep: true" not in renderer
    assert "requestAnimationFrame" in renderer


def test_builder_host_is_lazy_disposable_and_has_no_request_storm_observer() -> None:
    source = _read("apps/web/src/TenantVisualPageBuilder.vue")
    if not source:
        return
    assert "createSchedulerProAdapter" in source
    assert "ARGWS_VISUAL_BUILDER_VERSION" in source
    assert "document.createElement('argws-visual-builder')" in source
    assert "editor?.remove()" in source
    assert "await editor.load()" in source
    assert "MutationObserver" not in source
    assert "TenantPublicPageEditorV2" not in source


def test_control_plane_does_not_mount_obsolete_release_manager() -> None:
    main = _read("apps/admin/src/main.ts")
    if not main:
        return
    assert "scheduler-pro-visual-builder-manager" not in main
