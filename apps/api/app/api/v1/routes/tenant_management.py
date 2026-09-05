from contextlib import aclosing
from io import BytesIO
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_platform_tenant_access,
    get_platform_session,
    require_platform_permission,
)
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.db.session import tenant_session
from app.services.observability_service import ObservabilityService
from app.services.experience_service import ExperienceService
from app.services.file_service import TenantFileService
from app.services.branding_service import BrandingService
from app.services.tenant_access_resend_service import TenantAccessResendService
from app.services.tenant_management_service import TenantManagementService
from app.services.tenant_resolver import TenantResolver

router = APIRouter()

AdminBrandAssetKind = Literal["logo", "logo-dark", "icon", "favicon", "login-background"]
ADMIN_BRAND_ASSET_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml", "image/x-icon", "image/vnd.microsoft.icon"}
ADMIN_BRAND_ASSET_MAX_BYTES = 4 * 1024 * 1024
ADMIN_BRAND_ASSET_FIELDS = {"logo": "logo_url", "icon": "icon_url", "favicon": "favicon_url"}


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    timezone: str | None = Field(default=None, min_length=3, max_length=64)
    storage_quota_mb: int | None = Field(
        default=None,
        ge=128,
        le=1024 * 1024,
        description="Cota total do bucket do tenant em MiB.",
    )

    @model_validator(mode="after")
    def require_change(self) -> "TenantUpdateRequest":
        if (
            self.name is None
            and self.timezone is None
            and self.storage_quota_mb is None
        ):
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class TenantPrincipalAdminUpdateRequest(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    password: str | None = Field(default=None, min_length=12, max_length=128)

    @model_validator(mode="after")
    def require_change(self) -> "TenantPrincipalAdminUpdateRequest":
        if self.email is None and self.display_name is None and self.password is None:
            raise ValueError("Informe e-mail, nome ou nova senha.")
        return self


class TenantExperienceDraftRequest(BaseModel):
    html: str = Field(min_length=1)
    template_key: str | None = Field(default=None, max_length=160)
    bindings_values: dict[str, Any] = Field(default_factory=dict)
    theme: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    label: str | None = Field(default=None, max_length=180)


class TenantExperiencePublishRequest(BaseModel):
    version_id: str | None = None


class TenantBrandingAdminRequest(BaseModel):
    public_name: str | None = Field(default=None, max_length=160)
    slogan: str | None = Field(default=None, max_length=220)
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    font_family: str | None = Field(default=None, max_length=120)
    settings: dict[str, Any] | None = None


class TenantExperiencePolicyRequest(BaseModel):
    level: str = Field(pattern="^(blocked|basic|design|full|developer)$")
    apply_theme_to_console: bool | None = None


class TenantAccessResendRequest(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    generate_password: bool = False

    @model_validator(mode="after")
    def validate_password_mode(self) -> "TenantAccessResendRequest":
        if self.password is not None and self.generate_password:
            raise ValueError("Informe uma nova senha ou gere uma senha temporária, não ambos.")
        return self


@router.get("/{tenant_id}")
async def tenant_management_snapshot(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await TenantManagementService(session).snapshot(tenant_id))


@router.get("/{tenant_id}/logs")
async def tenant_management_logs(
    tenant_id: str,
    source: str | None = Query(default=None),
    service: str | None = Query(default=None),
    level: str | None = Query(default=None),
    integration: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    principal: AuthPrincipal = Depends(require_platform_permission("observability.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    """Return the consolidated operational history for one administered tenant."""

    assert_platform_tenant_access(principal, tenant_id)
    platform_rows = await ObservabilityService(session).list_platform_logs(
        tenant_filter=tenant_id,
        source=source,
        service=service,
        level=level,
        integration=integration,
        search=search,
        limit=limit,
    )
    rows: list[dict[str, Any]] = [
        {**row, "scope": "platform"} for row in platform_rows
    ]

    try:
        context = await TenantResolver(session).resolve_by_id(
            tenant_id,
            require_active=False,
        )
        async with aclosing(tenant_session(context)) as _session_scope_153:
            async for tenant_db in _session_scope_153:
                tenant_rows = await ObservabilityService(tenant_db).list_tenant_logs(
                    source=source,
                    service=service,
                    level=level,
                    integration=integration,
                    search=search,
                    limit=limit,
                )
                rows.extend({**row, "scope": "tenant"} for row in tenant_rows)
                break
    except Exception as exc:  # noqa: BLE001 - diagnostics must degrade gracefully
        rows.append(
            {
                "id": f"diagnostic-{tenant_id}",
                "source": "control-plane",
                "service": "tenant-management",
                "level": "WARNING",
                "event": "tenant_log_source_unavailable",
                "message": (
                    "O banco isolado do tenant não pôde ser consultado; exibindo "
                    "o histórico disponível no Control Plane."
                ),
                "details": {"error_type": type(exc).__name__},
                "scope": "platform",
                "created_at": None,
            }
        )

    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return success(rows[:limit])


@router.put("/{tenant_id}")
async def update_tenant_management(
    tenant_id: str,
    payload: TenantUpdateRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await TenantManagementService(session).update_tenant(
            tenant_id,
            name=payload.name,
            timezone=payload.timezone,
            storage_quota_mb=payload.storage_quota_mb,
            actor=principal.email,
        )
    )


@router.put("/{tenant_id}/principal-admin")
async def update_tenant_principal_admin(
    tenant_id: str,
    payload: TenantPrincipalAdminUpdateRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await TenantManagementService(session).update_principal_admin(
            tenant_id,
            email=str(payload.email) if payload.email is not None else None,
            display_name=payload.display_name,
            password=payload.password,
            actor=principal.email,
        )
    )


@router.post("/{tenant_id}/principal-admin/resend-access")
async def resend_tenant_principal_admin_access(
    tenant_id: str,
    payload: TenantAccessResendRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await TenantAccessResendService(session).resend(
            tenant_id,
            email=str(payload.email) if payload.email is not None else None,
            display_name=payload.display_name,
            password=payload.password,
            generate_password=payload.generate_password,
            actor=principal.email,
        )
    )


@router.get("/{tenant_id}/experience-policy")
async def tenant_experience_policy(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
    async with aclosing(tenant_session(context)) as _session_scope_252:
        async for tenant_db in _session_scope_252:
            rows = (
                await tenant_db.execute(
                    text(
                        "select key,value from tenant_settings "
                        "where key in ('experience_editor_level','experience_theme_apply_console')"
                    )
                )
            ).mappings().all()
            values = {str(row["key"]): row["value"] for row in rows}
            return success(
                {
                    "level": str(values.get("experience_editor_level") or "basic"),
                    "apply_theme_to_console": bool(values.get("experience_theme_apply_console") or False),
                }
            )
    return success({"level": "basic", "apply_theme_to_console": False})


@router.put("/{tenant_id}/experience-policy")
async def update_tenant_experience_policy(
    tenant_id: str,
    payload: TenantExperiencePolicyRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
    async with aclosing(tenant_session(context)) as _session_scope_280:
        async for tenant_db in _session_scope_280:
            import json

            await tenant_db.execute(
                text(
                    "insert into tenant_settings(key,value,updated_at) "
                    "values('experience_editor_level',cast(:level as jsonb),now()) "
                    "on conflict(key) do update set value=excluded.value,updated_at=now()"
                ),
                {"level": json.dumps(payload.level)},
            )
            if payload.apply_theme_to_console is not None:
                await tenant_db.execute(
                    text(
                        "insert into tenant_settings(key,value,updated_at) "
                        "values('experience_theme_apply_console',cast(:value as jsonb),now()) "
                        "on conflict(key) do update set value=excluded.value,updated_at=now()"
                    ),
                    {"value": json.dumps(payload.apply_theme_to_console)},
                )
            await tenant_db.commit()
            return success(
                {
                    "level": payload.level,
                    "apply_theme_to_console": bool(payload.apply_theme_to_console),
                }
            )
    return success({"level": payload.level, "apply_theme_to_console": False})


@router.get("/{tenant_id}/experience")
async def tenant_experience_snapshot(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
    branding = await BrandingService(session).manifest_for_context(context)
    async with aclosing(tenant_session(context)) as _session_scope_319:
        async for tenant_db in _session_scope_319:
            summary = await ExperienceService(tenant_db, context).summary()
            return success({"experience": summary, "branding": branding})
    return success({"experience": {"pages": []}, "branding": branding})


@router.get("/{tenant_id}/experience/pages/{surface}")
async def tenant_experience_page(
    tenant_id: str,
    surface: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
    async with aclosing(tenant_session(context)) as _session_scope_334:
        async for tenant_db in _session_scope_334:
            result = await ExperienceService(tenant_db, context).document(surface)
            return success(result)
    return success(None)


@router.post("/{tenant_id}/experience/pages/{surface}/draft")
async def tenant_experience_save_draft(
    tenant_id: str,
    surface: str,
    payload: TenantExperienceDraftRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
    async with aclosing(tenant_session(context)) as _session_scope_350:
        async for tenant_db in _session_scope_350:
            result = await ExperienceService(tenant_db, context).save_draft(
                surface, **payload.model_dump(), actor=None
            )
            return success(result)
    return success({})


@router.post("/{tenant_id}/experience/pages/{surface}/publish")
async def tenant_experience_publish(
    tenant_id: str,
    surface: str,
    payload: TenantExperiencePublishRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
    async with aclosing(tenant_session(context)) as _session_scope_368:
        async for tenant_db in _session_scope_368:
            return success(await ExperienceService(tenant_db, context).publish(surface, payload.version_id))
    return success({})


@router.put("/{tenant_id}/experience/branding")
async def tenant_experience_branding(
    tenant_id: str,
    payload: TenantBrandingAdminRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
    return success(
        await BrandingService(session).save_profile(
            tenant_id, payload.model_dump(exclude_none=True), tenant_name=context.slug
        )
    )


@router.post("/{tenant_id}/experience/branding/assets/{kind}")
async def tenant_experience_brand_asset(
    tenant_id: str,
    kind: AdminBrandAssetKind,
    file: UploadFile = File(...),
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    content_type = str(file.content_type or "").lower()
    if content_type not in ADMIN_BRAND_ASSET_TYPES:
        raise APIError("BRANDING_ASSET_TYPE_INVALID", "Envie PNG, JPEG, WebP, SVG ou ICO.", 422)
    try:
        data = await file.read(ADMIN_BRAND_ASSET_MAX_BYTES + 1)
    finally:
        await file.close()
    if not data or len(data) > ADMIN_BRAND_ASSET_MAX_BYTES:
        raise APIError("BRANDING_ASSET_INVALID", "O arquivo de marca deve possuir conteúdo e ter no máximo 4 MB.", 413)
    context = await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)
    stored = await TenantFileService(context).upload(f"branding/{kind}", BytesIO(data), content_type)
    public_url = f"/api/v1/branding/assets/{kind}"
    service = BrandingService(session)
    if kind in {"login-background", "logo-dark"}:
        profile = await service.get_or_create_profile(tenant_id, context.slug)
        settings = dict(profile.settings or {})
        settings["login_background_url" if kind == "login-background" else "logo_dark_url"] = public_url
        manifest = await service.save_profile(tenant_id, {"settings": settings}, tenant_name=context.slug)
    else:
        field = ADMIN_BRAND_ASSET_FIELDS.get(kind)
        if field is None:
            raise APIError("BRANDING_ASSET_KIND_INVALID", "Tipo de arquivo de marca inválido.", 422)
        manifest = await service.save_profile(tenant_id, {field: public_url}, tenant_name=context.slug)
    return success({"kind": kind, "url": public_url, "file": stored, "manifest": manifest})
