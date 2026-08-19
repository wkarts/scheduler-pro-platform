from app.api.v1.routes.downloads import _asset_target


def test_release_assets_are_mapped_as_universal_client_downloads() -> None:
    assert _asset_target("scheduler-pro-client-desktop-windows-v0.1.0-alpha.63.tar.gz") == (
        "desktop-windows",
        "installer-bundle",
    )
    assert _asset_target("scheduler-pro-client-desktop-linux-v0.1.0-alpha.63.tar.gz") == (
        "desktop-linux",
        "installer-bundle",
    )
    assert _asset_target("scheduler-pro-client-desktop-macos-v0.1.0-alpha.63.tar.gz") == (
        "desktop-macos",
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
    assert _asset_target("scheduler-pro-source-v0.1.0-alpha.63.zip") is None
