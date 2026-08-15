from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, get_tenant_context, require_permission
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.branding_service import BrandingService

router = APIRouter()


class BrandingProfileRequest(BaseModel):
    app_name: str | None = Field(default=None, max_length=160)
    public_name: str | None = Field(default=None, max_length=160)
    slogan: str | None = Field(default=None, max_length=220)
    logo_url: str | None = None
    icon_url: str | None = None
    favicon_url: str | None = None
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: str | None = Field(default=None, max_length=120)
    border_radius: str | None = Field(default=None, max_length=20)
    theme_mode: str | None = Field(default=None, pattern=r"^(light|dark|system)$")
    locale: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)
    settings: dict[str, Any] | None = None


class BuildProfileRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    target: str = Field(pattern=r"^(web|desktop|android|ios|pwa)$")
    bundle_identifier: str | None = Field(default=None, max_length=200)
    package_name: str | None = Field(default=None, max_length=200)
    api_url: str
    features: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/manifest")
async def get_manifest(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BrandingService(session)
    return success(await service.manifest_for_context(context))


@router.put("/profile")
async def save_profile(
    payload: BrandingProfileRequest,
    _: AuthPrincipal = Depends(require_permission("branding.manage")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BrandingService(session)
    data = payload.model_dump(exclude_none=True)
    return success(
        await service.save_profile(context.tenant_id, data, tenant_name=context.slug)
    )


@router.post("/publish")
async def publish_profile(
    _: AuthPrincipal = Depends(require_permission("branding.manage")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BrandingService(session)
    return success(await service.publish(context.tenant_id, tenant_name=context.slug))


@router.post("/build-profiles")
async def create_build_profile(
    payload: BuildProfileRequest,
    _: AuthPrincipal = Depends(require_permission("branding.manage")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BrandingService(session)
    return success(
        await service.create_build_profile(context.tenant_id, payload.model_dump())
    )
