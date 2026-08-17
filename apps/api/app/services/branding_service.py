from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import TenantContext
from app.db.models_platform import BuildProfile, TenantBrandingProfile

DEFAULT_COLORS = {
    "primary": "#118AF5",
    "secondary": "#00C2B8",
    "accent": "#00E5FF",
    "background": "#FFFFFF",
    "text": "#0B132B",
}
LEGACY_PLATFORM_COLORS = {
    "primary": "#2F6BFF",
    "secondary": "#22D3EE",
    "accent": "#1DAAF5",
    "background": "#F4F7FB",
    "text": "#0B1D3A",
}
DEFAULT_FONT_FAMILY = "Inter, Segoe UI, Arial, sans-serif"
DEFAULT_SLOGAN = "Agenda inteligente. Operação conectada."
DEFAULT_ICON_URL = "/icons/icon.svg"
DEFAULT_FAVICON_URL = "/favicon.svg"


def _normalized(value: str | None) -> str:
    return str(value or "").strip().lower()


class BrandingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _is_legacy_platform_default(profile: TenantBrandingProfile) -> bool:
        return (
            _normalized(profile.primary_color) == _normalized(LEGACY_PLATFORM_COLORS["primary"])
            and _normalized(profile.secondary_color) == _normalized(LEGACY_PLATFORM_COLORS["secondary"])
            and _normalized(profile.accent_color) == _normalized(LEGACY_PLATFORM_COLORS["accent"])
            and _normalized(profile.background_color) == _normalized(LEGACY_PLATFORM_COLORS["background"])
            and _normalized(profile.text_color) == _normalized(LEGACY_PLATFORM_COLORS["text"])
            and str(profile.font_family or "") == DEFAULT_FONT_FAMILY
        )

    @classmethod
    def _upgrade_legacy_platform_default(cls, profile: TenantBrandingProfile) -> bool:
        if not cls._is_legacy_platform_default(profile):
            return False
        profile.primary_color = DEFAULT_COLORS["primary"]
        profile.secondary_color = DEFAULT_COLORS["secondary"]
        profile.accent_color = DEFAULT_COLORS["accent"]
        profile.background_color = DEFAULT_COLORS["background"]
        profile.text_color = DEFAULT_COLORS["text"]
        return True

    @classmethod
    def _manifest_colors(cls, profile: TenantBrandingProfile) -> dict[str, str]:
        if cls._is_legacy_platform_default(profile):
            return dict(DEFAULT_COLORS)
        return {
            "primary": profile.primary_color or DEFAULT_COLORS["primary"],
            "secondary": profile.secondary_color or DEFAULT_COLORS["secondary"],
            "accent": profile.accent_color or DEFAULT_COLORS["accent"],
            "background": profile.background_color or DEFAULT_COLORS["background"],
            "text": profile.text_color or DEFAULT_COLORS["text"],
        }

    async def get_or_create_profile(self, tenant_id: str, tenant_name: str, timezone: str = "America/Bahia") -> TenantBrandingProfile:
        profile = (await self.session.execute(select(TenantBrandingProfile).where(TenantBrandingProfile.tenant_id == tenant_id))).scalar_one_or_none()
        if profile:
            return profile
        profile = TenantBrandingProfile(tenant_id=tenant_id, app_name=tenant_name, public_name=tenant_name, slogan=DEFAULT_SLOGAN, icon_url=DEFAULT_ICON_URL, favicon_url=DEFAULT_FAVICON_URL, primary_color=DEFAULT_COLORS["primary"], secondary_color=DEFAULT_COLORS["secondary"], accent_color=DEFAULT_COLORS["accent"], background_color=DEFAULT_COLORS["background"], text_color=DEFAULT_COLORS["text"], font_family=DEFAULT_FONT_FAMILY, border_radius="1rem", timezone=timezone)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def save_profile(self, tenant_id: str, payload: dict[str, Any], *, tenant_name: str | None = None) -> dict[str, Any]:
        profile = await self.get_or_create_profile(tenant_id, tenant_name or payload.get("public_name") or "Scheduler Pro")
        self._upgrade_legacy_platform_default(profile)
        allowed = {"app_name", "public_name", "slogan", "logo_url", "icon_url", "favicon_url", "primary_color", "secondary_color", "accent_color", "background_color", "text_color", "font_family", "border_radius", "theme_mode", "locale", "timezone", "settings"}
        for key, value in payload.items():
            if key in allowed:
                setattr(profile, key, value)
        profile.status = "DRAFT"
        profile.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(profile)
        return self.to_manifest(profile)

    async def publish(self, tenant_id: str, tenant_name: str = "Scheduler Pro") -> dict[str, Any]:
        profile = await self.get_or_create_profile(tenant_id, tenant_name)
        self._upgrade_legacy_platform_default(profile)
        profile.status = "PUBLISHED"
        profile.published_at = datetime.now(UTC)
        profile.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(profile)
        return self.to_manifest(profile)

    async def manifest_for_context(self, context: TenantContext) -> dict[str, Any]:
        profile = await self.get_or_create_profile(context.tenant_id, context.name if hasattr(context, "name") else context.slug)
        return self.to_manifest(profile, context=context)

    async def create_build_profile(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        profile = await self.get_or_create_profile(tenant_id, payload.get("name", "Scheduler Pro"))
        build = BuildProfile(tenant_id=tenant_id, branding_profile_id=profile.id, name=payload["name"], target=payload["target"], bundle_identifier=payload.get("bundle_identifier"), package_name=payload.get("package_name"), api_url=payload["api_url"], features=payload.get("features", []), config=payload.get("config", {}))
        self.session.add(build)
        await self.session.commit()
        await self.session.refresh(build)
        return {"id": build.id, "tenant_id": build.tenant_id, "branding_profile_id": build.branding_profile_id, "name": build.name, "target": build.target, "bundle_identifier": build.bundle_identifier, "package_name": build.package_name, "api_url": build.api_url, "features": build.features, "config": build.config}

    def to_manifest(self, profile: TenantBrandingProfile, context: TenantContext | None = None) -> dict[str, Any]:
        return {"tenant": {"id": profile.tenant_id, "slug": context.slug if context else None, "hostname": context.hostname if context else None}, "app": {"name": profile.app_name, "public_name": profile.public_name, "slogan": profile.slogan or DEFAULT_SLOGAN, "locale": profile.locale, "timezone": profile.timezone}, "assets": {"logo_url": profile.logo_url, "icon_url": profile.icon_url or DEFAULT_ICON_URL, "favicon_url": profile.favicon_url or DEFAULT_FAVICON_URL}, "theme": {"mode": profile.theme_mode, "font_family": profile.font_family or DEFAULT_FONT_FAMILY, "border_radius": profile.border_radius, "colors": self._manifest_colors(profile)}, "settings": profile.settings, "status": profile.status, "published_at": profile.published_at.isoformat() if profile.published_at else None}
