from pathlib import Path

from app.api.v1.routes.downloads import _asset_target

ROOT = Path(__file__).resolve().parents[3]


def test_release_assets_are_mapped_as_universal_client_downloads() -> None:
    assert _asset_target("scheduler-pro-client-desktop-windows-v0.1.0-alpha.63.tar.gz") == (
        "desktop-windows",
        "installer-bundle",
    )
    assert _asset_target("scheduler-pro-client-desktop-linux-v0.1.0-alpha.63.tar.gz") == (
        "desktop-linux",
        "installer-bundle",
    )
    assert _asset_target("scheduler-pro-client-android-v0.1.0-alpha.63-debug-installable.apk") == (
        "android",
        "apk",
    )
    assert _asset_target("scheduler-pro-client-ios-arm64-v0.1.0-alpha.63-unsigned.ipa") == (
        "ios",
        "ipa-unsigned",
    )
    assert _asset_target("scheduler-pro-admin-desktop-windows-v0.1.0-alpha.63.tar.gz") is None


def test_desktop_clients_are_webapp_shells_not_duplicated_business_frontends() -> None:
    for relative in ("apps/desktop/src/App.vue", "apps/admin-desktop/src/App.vue"):
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "window.location.replace" in content
        assert "instance_url" in content
        assert "appointments.value" not in content
        assert "customers.value" not in content
        assert "type ViewKey" not in content
        assert "type ModuleKey" not in content


def test_mobile_remains_a_dedicated_application_with_runtime_tenant_url() -> None:
    mobile = (ROOT / "apps/mobile/src/App.vue").read_text(encoding="utf-8")
    runtime = (ROOT / "apps/mobile/src/runtime-instance.ts").read_text(encoding="utf-8")
    main = (ROOT / "apps/mobile/src/main.ts").read_text(encoding="utf-8")
    assert "type TabKey" in mobile
    assert "appointment-cards" in mobile
    assert "window.location.replace" not in mobile
    assert "scheduler_pro_mobile_instance_url" in runtime
    assert "prepareMobileRuntimeInstance" in main


def test_web_tenant_exposes_universal_download_catalog_and_smart_agenda() -> None:
    app = (ROOT / "apps/web/src/App.vue").read_text(encoding="utf-8")
    assert "TenantUniversalDownloads" in app
    assert "TenantAgendaSmartWorkspace" in app
