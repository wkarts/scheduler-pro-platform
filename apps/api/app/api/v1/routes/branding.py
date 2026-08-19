from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_platform_session,
    get_tenant_context,
    require_permission,
    require_tenant_capability,
)
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


@router.get("/distribution")
async def tenant_distribution(
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    __: None = Depends(require_tenant_capability("builds")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    """Read-only distribution center for the authenticated tenant.

    Build orchestration stays in the Control Plane, but the tenant manager can see
    which profiles exist and download artifacts that were explicitly produced for
    its own tenant. No platform RBAC token is required and cross-tenant rows are
    impossible because every query is scoped by TenantContext.
    """

    profiles = (
        await session.execute(
            text(
                """
                select id::text, name, target, bundle_identifier, package_name,
                       api_url, features, config, created_at
                from build_profiles
                where tenant_id=cast(:tenant_id as uuid)
                order by target, name
                """
            ),
            {"tenant_id": context.tenant_id},
        )
    ).mappings().all()
    jobs = (
        await session.execute(
            text(
                """
                select id::text, target, status, workflow_run_id, source_ref,
                       source_sha, error, created_at, started_at, finished_at
                from build_jobs
                where tenant_id=cast(:tenant_id as uuid)
                order by created_at desc
                limit 100
                """
            ),
            {"tenant_id": context.tenant_id},
        )
    ).mappings().all()
    artifacts = (
        await session.execute(
            text(
                """
                select ba.id::text, ba.build_job_id::text, ba.target,
                       ba.artifact_type, ba.name, ba.download_url,
                       ba.checksum_sha256, ba.size_bytes, ba.metadata,
                       ba.created_at
                from build_artifacts ba
                where ba.tenant_id=cast(:tenant_id as uuid)
                order by ba.created_at desc
                limit 200
                """
            ),
            {"tenant_id": context.tenant_id},
        )
    ).mappings().all()
    return success(
        {
            "tenant_id": context.tenant_id,
            "hostname": context.hostname,
            "profiles": [dict(row) for row in profiles],
            "jobs": [dict(row) for row in jobs],
            "artifacts": [dict(row) for row in artifacts],
        }
    )


@router.put("/profile")
async def save_profile(
    payload: BrandingProfileRequest,
    _: AuthPrincipal = Depends(require_permission("branding.manage")),
    __: None = Depends(require_tenant_capability("branding")),
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
    __: None = Depends(require_tenant_capability("branding")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BrandingService(session)
    return success(await service.publish(context.tenant_id, tenant_name=context.slug))


@router.post("/build-profiles")
async def create_build_profile(
    payload: BuildProfileRequest,
    _: AuthPrincipal = Depends(require_permission("branding.manage")),
    __: None = Depends(require_tenant_capability("builds")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BrandingService(session)
    return success(
        await service.create_build_profile(context.tenant_id, payload.model_dump())
    )
