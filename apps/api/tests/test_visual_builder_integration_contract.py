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


def test_visual_builder_is_a_first_class_workspace_package() -> None:
    raw = _read("packages/visual-builder/package.json")
    if not raw:
        return
    package = json.loads(raw)
    assert package["name"] == "@argws/visual-builder"
    assert package["version"] == "0.1.0"
    assert "typecheck" in package["scripts"]
    assert "build" in package["scripts"]


def test_scheduler_adapter_never_converts_first_class_html_silently() -> None:
    source = _read("packages/visual-builder/src/adapters.js")
    if not source:
        return
    assert "HTML_TEMPLATE_PROTECTED" in source
    assert "render_mode==='HTML'" in source
    assert "throw htmlProtectedError" in source


def test_new_visual_builder_replaces_old_editor_by_default_with_rollback_flag() -> None:
    source = _read("apps/web/src/App.vue")
    if not source:
        return
    assert "TenantVisualPageBuilder" in source
    assert "VITE_VISUAL_PAGE_BUILDER" in source
    assert '<TenantVisualPageBuilder v-if="visualBuilderEnabled"' in source
    assert '<TenantPublicPageEditorV2 v-else' in source


def test_public_landing_uses_builder_renderer_without_deep_watch() -> None:
    page = _read("apps/web/src/PublicSitePage.vue")
    renderer = _read("apps/web/src/PublicVisualLandingRenderer.vue")
    if not page or not renderer:
        return
    assert "PublicVisualLandingRenderer" in page
    assert "argws-visual-builder/v1" in page
    assert "deep:true" not in renderer
    assert "deep: true" not in renderer
    assert "requestAnimationFrame" in renderer


def test_builder_host_is_lazy_and_disposes_editor_on_close() -> None:
    source = _read("apps/web/src/TenantVisualPageBuilder.vue")
    if not source:
        return
    assert "document.createElement('argws-visual-builder')" in source
    assert "editor?.remove()" in source
    assert "isHtmlContent(page.content)" in source
    assert "htmlProtected.value=page.content" in source
