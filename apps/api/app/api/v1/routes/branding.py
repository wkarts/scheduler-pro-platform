from collections.abc import Iterator
from io import BytesIO
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, StreamingResponse

from app.api.deps import (
    get_platform_session,
    get_tenant_context,
    require_permission,
    require_tenant_capability,
)
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.branding_service import BrandingService
from app.services.file_service import TenantFileService

router = APIRouter()
BrandAssetKind = Literal["logo", "logo-dark", "icon", "favicon", "login-background"]
BRAND_ASSET_FIELDS = {"logo": "logo_url", "icon": "icon_url", "favicon": "favicon_url"}
BRAND_ASSET_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon"}
BRAND_ASSET_MAX_BYTES = 4 * 1024 * 1024


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


def _stream(body: Any) -> Iterator[bytes]:
    try:
        yield from body.iter_chunks(chunk_size=64 * 1024)
    finally:
        body.close()


@router.get("/manifest")
async def get_manifest(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BrandingService(session)
    return success(await service.manifest_for_context(context))


@router.get("/manifest.webmanifest")
async def tenant_pwa_manifest(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> JSONResponse:
    manifest = await BrandingService(session).manifest_for_context(context)
    app = manifest["app"]
    assets = manifest["assets"]
    theme = manifest["theme"]
    icon_url = str(assets.get("icon_url") or "")
    if icon_url and icon_url not in {"/icons/icon-512.png", "/icons/icon.svg"}:
        icons = [{"src": icon_url, "sizes": "any", "type": "image/png", "purpose": "any maskable"}]
    else:
        icons = [
            {"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icons/maskable-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ]
    payload = {
        "id": f"/{context.slug}",
        "name": app.get("public_name") or app.get("name") or "Scheduler PRO",
        "short_name": (app.get("public_name") or "Scheduler PRO")[:30],
        "description": app.get("slogan") or "Mais tempo para o que realmente importa.",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": theme["colors"].get("background") or "#FFFFFF",
        "theme_color": theme["colors"].get("secondary") or "#0B0F1A",
        "icons": icons,
        "categories": ["business", "productivity"],
        "shortcuts": [
            {"name": "Agenda", "url": "/#agenda"},
            {"name": "Página pública", "url": "/pagina"},
            {"name": "Agendar", "url": "/agendar"},
        ],
    }
    return JSONResponse(payload, media_type="application/manifest+json", headers={"Cache-Control": "public, max-age=300, must-revalidate"})


@router.get("/assets/{kind}")
async def public_brand_asset(
    kind: BrandAssetKind,
    context: TenantContext = Depends(get_tenant_context),
) -> StreamingResponse:
    result = await TenantFileService(context).get_object(f"branding/{kind}")
    return StreamingResponse(
        _stream(result["Body"]),
        media_type=str(result.get("ContentType") or "application/octet-stream"),
        headers={
            "Cache-Control": "public, max-age=300, must-revalidate",
            "ETag": str(result.get("ETag", "")),
        },
    )


@router.post("/assets/{kind}")
async def upload_brand_asset(
    kind: BrandAssetKind,
    file: UploadFile = File(...),
    _: AuthPrincipal = Depends(require_permission("branding.manage")),
    __: None = Depends(require_tenant_capability("branding")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    content_type = str(file.content_type or "").lower()
    if content_type not in BRAND_ASSET_TYPES:
        raise APIError(
            "BRANDING_ASSET_TYPE_INVALID",
            "Envie PNG, JPEG, WebP, SVG ou ICO.",
            422,
        )
    try:
        data = await file.read(BRAND_ASSET_MAX_BYTES + 1)
    finally:
        await file.close()
    if not data:
        raise APIError("BRANDING_ASSET_EMPTY", "Arquivo de marca vazio.", 422)
    if len(data) > BRAND_ASSET_MAX_BYTES:
        raise APIError(
            "BRANDING_ASSET_TOO_LARGE",
            "O arquivo de marca deve ter no máximo 4 MB.",
            413,
        )
    stored = await TenantFileService(context).upload(
        f"branding/{kind}", BytesIO(data), content_type
    )
    public_url = f"/api/v1/branding/assets/{kind}"
    service = BrandingService(session)
    if kind in {"login-background", "logo-dark"}:
        profile = await service.get_or_create_profile(context.tenant_id, context.slug)
        settings = dict(profile.settings or {})
        settings["login_background_url" if kind == "login-background" else "logo_dark_url"] = public_url
        manifest = await service.save_profile(
            context.tenant_id,
            {"settings": settings},
            tenant_name=context.slug,
        )
    else:
        manifest = await service.save_profile(
            context.tenant_id,
            {BRAND_ASSET_FIELDS[kind]: public_url},
            tenant_name=context.slug,
        )
    return success({"kind": kind, "url": public_url, "file": stored, "manifest": manifest})


@router.get("/distribution")
async def tenant_distribution(
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    __: None = Depends(require_tenant_capability("builds")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
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
    return success(await service.save_profile(context.tenant_id, data, tenant_name=context.slug))


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
    return success(await service.create_build_profile(context.tenant_id, payload.model_dump()))
