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


def test_navigation_is_not_driven_by_dom_mutation_or_click_bridges() -> None:
    main = _read("apps/web/src/main.ts")
    app = _read("apps/web/src/App.vue")
    console = _read("apps/web/src/TenantConsole.vue")
    if not main:
        return
    assert "installTenantNavigationRuntime" not in main
    assert "installTenantExtensionNavigationBridge" not in main
    assert "TenantWorkspaceCoordinator" not in app
    assert "window.location.hash = key" in console


def test_global_fetch_shares_identical_inflight_reads() -> None:
    source = _read("apps/web/src/tenant-auth-fetch.ts")
    if not source:
        return
    assert "inflightReads" in source
    assert "method === 'GET'" in source
    assert ".clone()" in source
    assert "isRealtimeOrStreaming" in source


def test_auxiliary_tenant_surfaces_are_route_driven_not_dom_observers() -> None:
    smtp = _read("apps/web/src/TenantMailModeSelector.vue")
    config = _read("apps/web/src/TenantConfigurationCenter.vue")
    booking = _read("apps/web/src/TenantBookingAndMessages.vue")
    if smtp:
        assert "MutationObserver" not in smtp
        assert "hashchange" in smtp
    if config:
        assert "MutationObserver" not in config
        assert "#configuracoes" in config
    if booking:
        assert "MutationObserver" not in booking
        assert "#agenda-publica" in booking
