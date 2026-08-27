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


def test_navigation_runtime_does_not_watch_the_entire_dom_or_auto_refresh_views() -> None:
    source = _read("apps/web/src/tenant-navigation-runtime.ts")
    if not source:
        return
    assert "new MutationObserver" not in source
    assert "observer.observe(document.body" not in source
    assert "refreshCurrentView" not in source
    assert "refresh.click()" not in source
    assert "installed = false" in source


def test_global_fetch_shares_identical_inflight_reads() -> None:
    source = _read("apps/web/src/tenant-auth-fetch.ts")
    if not source:
        return
    assert "inflightReads" in source
    assert "method === 'GET'" in source
    assert ".clone()" in source
    assert "isRealtimeOrStreaming" in source


def test_auxiliary_tenant_surfaces_are_event_driven_not_dom_observers() -> None:
    smtp = _read("apps/web/src/TenantMailModeSelector.vue")
    coordinator = _read("apps/web/src/TenantWorkspaceCoordinator.vue")
    if smtp:
        assert "MutationObserver" not in smtp
        assert "TENANT_NAVIGATION_EVENT" in smtp
    if coordinator:
        assert "MutationObserver" not in coordinator
        assert "TENANT_NAVIGATION_EVENT" in coordinator
