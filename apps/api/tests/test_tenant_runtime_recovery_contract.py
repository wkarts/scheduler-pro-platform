from pathlib import Path


def _root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "web" / "src").is_dir():
            return parent
    return None


def _read(relative: str) -> str:
    root = _root()
    if root is None:
        import pytest

        pytest.skip("Fontes Web não estão disponíveis nesta imagem isolada da API.")
    return (root / relative).read_text(encoding="utf-8")


def test_tenant_bootstrap_does_not_mutate_vue_dom_from_external_observer() -> None:
    root = _root()
    if root is None:
        import pytest

        pytest.skip("Fontes Web não estão disponíveis nesta imagem isolada da API.")
    main = _read("apps/web/src/main.ts")
    assert "installTenantVersionBadge" not in main
    assert not (root / "apps/web/src/tenant-version-badge.ts").exists()
    assert "createApp(App).use(createPinia()).mount('#app')" in main


def test_service_worker_forces_cache_generation_after_runtime_recovery() -> None:
    sw = _read("apps/web/public/sw.js")
    assert "scheduler-pro-web-" in sw
    assert "tenant-runtime-recovery-v7" in sw
    assert "self.skipWaiting()" in sw
    assert "self.clients.claim()" in sw
    assert "caches.delete(key)" in sw
    assert "request.mode === 'navigate'" in sw
    assert "networkFirst(request, '/offline.html')" in sw


def test_alpha95_visual_builder_and_checkin_fix_remain_present() -> None:
    frame = _read("apps/web/src/HtmlTemplateFrame.vue")
    main = _read("apps/web/src/main.ts")
    assert "function cloneForBridge(value:any):any" in frame
    assert "target.postMessage(cloneForBridge(message),'*')" in frame
    assert "import './tenant-overlay-layering.css'" in main
