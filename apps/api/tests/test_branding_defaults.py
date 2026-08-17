from types import SimpleNamespace

from app.services.branding_service import BrandingService, DEFAULT_COLORS, LEGACY_PLATFORM_COLORS


def legacy_profile(**overrides: str) -> SimpleNamespace:
    values = {
        "primary_color": LEGACY_PLATFORM_COLORS["primary"],
        "secondary_color": LEGACY_PLATFORM_COLORS["secondary"],
        "accent_color": LEGACY_PLATFORM_COLORS["accent"],
        "background_color": LEGACY_PLATFORM_COLORS["background"],
        "text_color": LEGACY_PLATFORM_COLORS["text"],
        "font_family": "Inter, Segoe UI, Arial, sans-serif",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_legacy_platform_defaults_render_as_official_brand() -> None:
    profile = legacy_profile()
    assert BrandingService._is_legacy_platform_default(profile)
    assert BrandingService._manifest_colors(profile) == DEFAULT_COLORS


def test_custom_tenant_branding_is_not_rewritten() -> None:
    profile = legacy_profile(primary_color="#AA00CC")
    assert not BrandingService._is_legacy_platform_default(profile)
    assert BrandingService._manifest_colors(profile)["primary"] == "#AA00CC"


def test_upgrade_only_changes_known_platform_default_profile() -> None:
    profile = legacy_profile()
    assert BrandingService._upgrade_legacy_platform_default(profile)
    assert profile.primary_color == DEFAULT_COLORS["primary"]
    assert profile.secondary_color == DEFAULT_COLORS["secondary"]
    assert profile.accent_color == DEFAULT_COLORS["accent"]
    assert profile.background_color == DEFAULT_COLORS["background"]
    assert profile.text_color == DEFAULT_COLORS["text"]
