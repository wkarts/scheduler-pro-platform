from __future__ import annotations

from typing import Any, Literal
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_platform_session, get_tenant_context, get_tenant_session, require_permission
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.experience_contract_service import ExperienceContractService, ParsedExperience
from app.services.builtin_template_package_service import (
    OFFICIAL_TEMPLATE_KEYS,
    builtin_template_archive,
    official_template_families,
)
from app.services.experience_service import ExperienceService
from app.services.file_service import TenantFileService
from app.services.global_template_service import GlobalTemplateService
from app.services.html_template_contract import HtmlTemplateContract

router = APIRouter()
Surface = Literal["LANDING", "BOOKING"]


class DraftRequest(BaseModel):
    html: str = Field(min_length=1)
    template_key: str | None = Field(default=None, max_length=160)
    bindings_values: dict[str, Any] = Field(default_factory=dict)
    theme: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    label: str | None = Field(default=None, max_length=180)


class PublishRequest(BaseModel):
    version_id: str | None = None


class EnabledRequest(BaseModel):
    enabled: bool


class EditorPolicyRequest(BaseModel):
    level: Literal["blocked", "basic", "design", "full", "developer"]


class PwaRequest(BaseModel):
    open_mode: Literal["AUTO", "LOGIN", "DASHBOARD", "LANDING"] = "AUTO"


class ThemePolicyRequest(BaseModel):
    apply_to_console: bool


class MarketingRequest(BaseModel):
    ga4_measurement_id: str | None = Field(default=None, max_length=80)
    google_ads_conversion_id: str | None = Field(default=None, max_length=80)
    google_ads_conversion_label: str | None = Field(default=None, max_length=120)
    meta_pixel_id: str | None = Field(default=None, max_length=80)
    gtm_container_id: str | None = Field(default=None, max_length=80)
    tiktok_pixel_id: str | None = Field(default=None, max_length=80)


async def _service(session: AsyncSession, context: TenantContext) -> ExperienceService:
    return ExperienceService(session, context)


@router.get("")
async def summary(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await (await _service(session, context)).summary())


@router.get("/pages/{surface}")
async def page_document(
    surface: Surface,
    published: bool = False,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    result = await (await _service(session, context)).document(surface, published=published)
    if result is None:
        raise APIError("EXPERIENCE_PAGE_NOT_FOUND", "Página ainda não inicializada.", 404)
    return success(result)


@router.post("/pages/{surface}/draft")
async def save_draft(
    surface: Surface,
    payload: DraftRequest,
    principal: AuthPrincipal = Depends(get_current_user),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await (await _service(session, context)).save_draft(surface, **payload.model_dump(), actor=principal.user_id))


@router.post("/pages/{surface}/publish")
async def publish(
    surface: Surface,
    payload: PublishRequest,
    _: AuthPrincipal = Depends(get_current_user),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await (await _service(session, context)).publish(surface, payload.version_id))


@router.get("/pages/{surface}/versions")
async def versions(
    surface: Surface,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await (await _service(session, context)).versions(surface))


@router.put("/pages/{surface}/enabled")
async def enabled(
    surface: Surface,
    payload: EnabledRequest,
    _: AuthPrincipal = Depends(get_current_user),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await (await _service(session, context)).set_enabled(surface, payload.enabled))


@router.post("/assets")
async def upload_experience_asset(
    file: UploadFile = File(...),
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    content_type = str(file.content_type or "application/octet-stream").lower()
    allowed = {
        "image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/gif",
        "video/mp4", "application/json", "font/woff", "font/woff2",
    }
    if content_type not in allowed:
        raise APIError("EXPERIENCE_ASSET_TYPE_INVALID", "Tipo de asset não permitido.", 422)
    try:
        data = await file.read(12 * 1024 * 1024 + 1)
    finally:
        await file.close()
    if not data:
        raise APIError("EXPERIENCE_ASSET_EMPTY", "Arquivo vazio.", 422)
    if len(data) > 12 * 1024 * 1024:
        raise APIError("EXPERIENCE_ASSET_TOO_LARGE", "Asset deve ter no máximo 12 MB.", 413)
    suffix = Path(file.filename or "asset").suffix.lower()[:12]
    storage_key = f"experience/user/{uuid4().hex}{suffix}"
    stored = await TenantFileService(context).upload(storage_key, BytesIO(data), content_type)
    return success(
        {
            "url": f"/api/v1/public/assets/{storage_key}",
            "storage_key": storage_key,
            "content_type": content_type,
            "size_bytes": int(stored["size_bytes"]),
        }
    )


@router.get("/templates")
async def experience_templates(
    _: AuthPrincipal = Depends(get_current_user),
    context: TenantContext = Depends(get_tenant_context),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    families: list[dict[str, Any]] = []
    official_keys = set(OFFICIAL_TEMPLATE_KEYS)
    for item in official_template_families():
        families.append(
            {
                "key": item["key"],
                "name": item["name"],
                "description": item.get("description"),
                "segment": item.get("segment"),
                "platform_default": item.get("platform_default", False),
                "surfaces": ["LANDING", "BOOKING"],
                "source_schema": item.get("source_schema") or "argws-experience-package/v2",
                "package_version": item.get("package_version"),
                "source": "official-package",
            }
        )
    rows = await GlobalTemplateService(platform).list(surface="LANDING", tenant_id=context.tenant_id)
    for row in rows:
        key = str(row.get("key") or "")
        if not key or key in official_keys:
            continue
        families.append(
            {
                "key": key,
                "name": row.get("name") or key,
                "description": row.get("description"),
                "segment": row.get("segment"),
                "platform_default": bool(row.get("default_for_new_tenants", False)),
                "surfaces": ["LANDING", "BOOKING"],
                "source_schema": "argws-experience-package/v2",
                "source": "control-plane",
                "template_id": row.get("id"),
            }
        )
    return success(families)


@router.post("/import-official/{template_key}")
async def import_official_experience(
    template_key: str,
    principal: AuthPrincipal = Depends(require_permission("tenant.manage")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    if template_key in OFFICIAL_TEMPLATE_KEYS:
        parsed = ExperienceContractService.parse_archive(builtin_template_archive(template_key))
    else:
        service = GlobalTemplateService(platform)
        landing = await service.content(surface="LANDING", key=template_key, tenant_id=context.tenant_id)
        booking = await service.content(surface="BOOKING", key=template_key, tenant_id=context.tenant_id)
        landing_content = landing["version"]["content"]
        booking_content = booking["version"]["content"]
        if not HtmlTemplateContract.is_html_content(landing_content) or not HtmlTemplateContract.is_html_content(booking_content):
            raise APIError("EXPERIENCE_TEMPLATE_INVALID", "O modelo do Control Plane não é uma experiência HTML compatível.", 409)
        meta = landing_content.get("experience") if isinstance(landing_content.get("experience"), dict) else {}
        parsed = ParsedExperience(
            source_schema=str(meta.get("schema") or "argws-experience-package/v2"),
            package_key=template_key,
            name=str(landing.get("name") or template_key),
            description="",
            landing_html=str(landing_content["html_document"]),
            booking_html=str(booking_content["html_document"]),
            bindings=meta.get("bindings") if isinstance(meta.get("bindings"), dict) else {},
            theme=meta.get("theme") if isinstance(meta.get("theme"), dict) else {},
            assets=(),
            warnings=("Modelo carregado da biblioteca do Control Plane; assets já incorporados ao HTML.",),
        )
    return success(
        await (await _service(session, context)).import_package(parsed, actor=principal.user_id)
    )


@router.post("/import")
async def import_experience(
    file: UploadFile = File(...),
    principal: AuthPrincipal = Depends(require_permission("tenant.manage")),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    try:
        data = await file.read(50 * 1024 * 1024 + 1)
    finally:
        await file.close()
    parsed = ExperienceContractService.parse_archive(data)
    return success(await (await _service(session, context)).import_package(parsed, actor=principal.user_id))


@router.put("/editor-policy")
async def editor_policy(
    payload: EditorPolicyRequest,
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    await session.execute(
        text("insert into tenant_settings(key,value,updated_at) values('experience_editor_level',cast(:value as jsonb),now()) on conflict(key) do update set value=excluded.value,updated_at=now()"),
        {"value": __import__("json").dumps(payload.level)},
    )
    await session.commit()
    return success({"level": payload.level})


@router.put("/marketing")
async def marketing(
    payload: MarketingRequest,
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    value = payload.model_dump(exclude_none=True)
    await session.execute(
        text("insert into tenant_settings(key,value,updated_at) values('marketing_analytics',cast(:value as jsonb),now()) on conflict(key) do update set value=excluded.value,updated_at=now()"),
        {"value": __import__("json").dumps(value)},
    )
    await session.commit()
    return success(value)


@router.put("/pwa")
async def pwa_settings(
    payload: PwaRequest,
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    import json
    await session.execute(
        text("insert into tenant_settings(key,value,updated_at) values('pwa_open_mode',cast(:value as jsonb),now()) on conflict(key) do update set value=excluded.value,updated_at=now()"),
        {"value": json.dumps(payload.open_mode)},
    )
    await session.commit()
    return success({"open_mode": payload.open_mode})


@router.put("/theme-policy")
async def theme_policy(
    payload: ThemePolicyRequest,
    _: AuthPrincipal = Depends(require_permission("tenant.manage")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    import json
    await session.execute(
        text("insert into tenant_settings(key,value,updated_at) values('experience_theme_apply_console',cast(:value as jsonb),now()) on conflict(key) do update set value=excluded.value,updated_at=now()"),
        {"value": json.dumps(payload.apply_to_console)},
    )
    await session.commit()
    return success({"apply_to_console": payload.apply_to_console})
