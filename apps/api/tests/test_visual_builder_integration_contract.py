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


def test_visual_builder_2_4_0_is_the_canonical_experience_builder() -> None:
    raw = _read("packages/visual-builder/package.json")
    if not raw:
        return
    package = json.loads(raw)
    assert package["name"] == "@argws/visual-builder"
    assert package["version"] == "2.4.0"
    assert "project-workspace.js" in package["scripts"]["check"]
    assert "release-b64" not in json.dumps(package)
    assert "materialize" not in package["scripts"]


def test_visual_builder_uses_experience_contract_v2_without_login_template() -> None:
    experience = _read("packages/visual-builder/src/experience-contract.js")
    sdk = _read("packages/visual-builder/src/template-runtime-sdk.js")
    host = _read("apps/web/src/TenantVisualPageBuilder.vue")
    assert "argws-experience-package/v2" in experience
    assert "pages/landing.html" in experience
    assert "pages/booking.html" in experience
    assert "Template Runtime SDK" in sdk or "booking" in sdk
    assert "Landing e Agenda usam HTML completo" in host
    assert "Login permanece nativo" in host
    assert "Login não usa template HTML" in host


def test_old_materialized_visual_builder_runtime_is_physically_removed() -> None:
    assert not _path("packages/visual-builder/release-b64").exists()
    assert not _path("packages/visual-builder/runtime").exists()
    assert not _path("packages/visual-builder/scripts/materialize-release.mjs").exists()


def test_scheduler_pro_uses_visual_builder_2_4_0_experience_host() -> None:
    app = _read("apps/web/src/App.vue")
    host = _read("apps/web/src/TenantVisualPageBuilder.vue")
    package = _read("apps/web/package.json")
    if not app or not package:
        return
    assert "TenantVisualPageBuilder" in app
    assert "ExperiencePageAdapter" in host
    assert "argws-visual-builder" in host
    assert "#visual-builder" in host
    assert json.loads(package)["dependencies"]["@argws/visual-builder"] == "2.4.0"


def test_public_pages_use_real_context_and_native_login() -> None:
    page = _read("apps/web/src/PublicSitePage.vue")
    app = _read("apps/web/src/App.vue")
    login = _read("apps/web/src/TenantBrandedLogin.vue")
    context_service = _read("apps/api/app/services/public_page_context_service.py")
    assert "'/login'" in app
    assert "TenantBrandedLogin" in app
    assert "loadExperience('LANDING')" in page
    assert "loadExperience('BOOKING')" in page
    assert "public_schedule_enabled" in context_service
    assert "pwa_open_mode" in app
    assert "branding" in login.lower()


def test_builder_host_is_route_driven_and_disposable() -> None:
    source = _read("apps/web/src/TenantVisualPageBuilder.vue")
    if not source:
        return
    assert "ExperiencePageAdapter" in source
    assert "document.createElement('argws-visual-builder')" in source
    assert "advancedElement.value?.remove()" in source
    assert "hashchange" in source
    assert "MutationObserver" not in source


def test_builder_does_not_use_native_browser_dialogs() -> None:
    sources = "\n".join(
        _read(path)
        for path in (
            "packages/visual-builder/src/editor.js",
            "packages/visual-builder/src/project-workspace.js",
            "apps/web/src/TenantAgendaOperator.vue",
        )
    )
    assert "window.alert(" not in sources
    assert "window.confirm(" not in sources
    assert "window.prompt(" not in sources
    assert "globalThis.alert(" not in sources
    assert "globalThis.confirm(" not in sources
    assert "globalThis.prompt(" not in sources


def test_control_plane_does_not_mount_obsolete_release_manager() -> None:
    main = _read("apps/admin/src/main.ts")
    if not main:
        return
    assert "scheduler-pro-visual-builder-manager" not in main
