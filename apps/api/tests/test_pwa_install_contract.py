from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_pwa_manifest_and_service_worker_are_present() -> None:
    manifest = (ROOT / "apps/web/public/manifest.webmanifest").read_text(encoding="utf-8")
    pwa = (ROOT / "apps/web/src/pwa.ts").read_text(encoding="utf-8")
    assert '"display": "standalone"' in manifest
    assert '"start_url": "/#dashboard"' in manifest
    assert "navigator.serviceWorker.register('/sw.js')" in pwa
    assert "beforeinstallprompt" in pwa
    assert "appinstalled" in pwa


def test_pwa_install_is_exposed_before_and_after_login_and_in_apps() -> None:
    app = (ROOT / "apps/web/src/App.vue").read_text(encoding="utf-8")
    surface = (ROOT / "apps/web/src/TenantPwaInstallSurface.vue").read_text(encoding="utf-8")
    downloads = (ROOT / "apps/web/src/TenantUniversalDownloads.vue").read_text(encoding="utf-8")
    assert "TenantPwaInstallSurface" in app
    assert ".tenant-login-card" in surface
    assert ".tenant-console .topbar" in surface
    assert "Web App / PWA" in downloads
    assert "Adicionar à Tela de Início" in downloads
