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


def test_visual_builder_2_3_0_is_the_canonical_page_workspace() -> None:
    raw = _read("packages/visual-builder/package.json")
    if not raw:
        return
    package = json.loads(raw)
    assert package["name"] == "@argws/visual-builder"
    assert package["version"] == "2.3.0"
    assert "project-workspace.js" in package["scripts"]["check"]
    assert "release-b64" not in json.dumps(package)
    assert "materialize" not in package["scripts"]


def test_visual_builder_uses_pages_first_class_and_scheduler_families() -> None:
    project = _read("packages/visual-builder/src/project.js")
    workspace = _read("packages/visual-builder/src/project-workspace.js")
    templates = _read("packages/visual-builder/src/template-packages.js")
    assert "createProjectPage" in project
    assert "Projeto / Site" in workspace
    assert "Modelos oficiais" in workspace
    assert "importSchedulerProTemplateFamily" in templates
    assert "landing.html e agendamento.html viram páginas independentes" in templates
    assert "html_surface" not in workspace


def test_old_materialized_visual_builder_runtime_is_physically_removed() -> None:
    assert not _path("packages/visual-builder/release-b64").exists()
    assert not _path("packages/visual-builder/runtime").exists()
    assert not _path("packages/visual-builder/scripts/materialize-release.mjs").exists()


def test_scheduler_pro_uses_visual_builder_2_3_0_project_adapter() -> None:
    app = _read("apps/web/src/App.vue")
    host = _read("apps/web/src/TenantVisualPageBuilder.vue")
    package = _read("apps/web/package.json")
    if not app or not package:
        return
    assert "TenantVisualPageBuilder" in app
    assert "SchedulerProProjectAdapter" in host
    assert "argws-visual-builder-app" in host
    assert "#visual-builder" in host
    assert json.loads(package)["dependencies"]["@argws/visual-builder"] == "2.3.0"


def test_public_pages_use_first_class_page_renderer() -> None:
    page = _read("apps/web/src/PublicSitePage.vue")
    renderer = _read("apps/web/src/PublicVisualLandingRenderer.vue")
    if not page or not renderer:
        return
    assert "PublicVisualLandingRenderer" in page
    assert "argws-page-renderer" in renderer
    assert "PageDocument" in renderer
    assert "MutationObserver" not in renderer


def test_builder_host_is_route_driven_and_disposable() -> None:
    source = _read("apps/web/src/TenantVisualPageBuilder.vue")
    if not source:
        return
    assert "SchedulerProProjectAdapter" in source
    assert "document.createElement('argws-visual-builder-app')" in source
    assert "app?.remove()" in source
    assert "hashchange" in source
    assert "MutationObserver" not in source


def test_control_plane_does_not_mount_obsolete_release_manager() -> None:
    main = _read("apps/admin/src/main.ts")
    if not main:
        return
    assert "scheduler-pro-visual-builder-manager" not in main
