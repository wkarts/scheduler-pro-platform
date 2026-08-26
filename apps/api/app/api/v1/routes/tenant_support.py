import json
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_platform_tenant_access,
    get_platform_session,
    require_platform_permission,
)
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.db.session import tenant_session
from app.services.booking_parameters_service import BookingParametersService
from app.services.branding_service import BrandingService
from app.services.global_template_service import GlobalTemplateService
from app.services.landing_service import LandingPageService
from app.services.template_contract import TemplateContract
from app.services.tenant_resolver import TenantResolver

router = APIRouter()


class BookingParametersAdminUpdate(BaseModel):
    service_mode: str = "REQUIRED"
    email_mode: str = "OPTIONAL"
    phone_mode: str = "REQUIRED"
    duration_mode: str = "REQUIRED"
    professional_mode: str = "REQUIRED"
    default_duration_minutes: int = Field(default=60, ge=5, le=720)
    default_professional_name: str = Field(default="Agenda geral", min_length=2, max_length=160)
    default_customer_mode: str = "NEW"
    simultaneous: dict[str, Any] = Field(default_factory=dict)
    rules: dict[str, Any] = Field(default_factory=dict)
    minimum_notice_minutes: int = Field(default=1440, ge=0, le=525600)
    phone: dict[str, Any] = Field(default_factory=dict)


class GlobalTemplateApply(BaseModel):
    template_id: str
    version_number: int | None = Field(default=None, ge=1)
    publish: bool = False


class LandingPublish(BaseModel):
    version_id: str | None = None


class BookingPageSettingsUpdate(BaseModel):
    values: dict[str, Any]


async def _context(session: AsyncSession, tenant_id: str) -> TenantContext:
    return await TenantResolver(session).resolve_by_id(tenant_id, require_active=False)


@router.get("/{tenant_id}/booking-parameters")
async def tenant_booking_parameters_support(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        return success(await BookingParametersService(database).get())
    return success({})


@router.put("/{tenant_id}/booking-parameters")
async def update_tenant_booking_parameters_support(
    tenant_id: str,
    payload: BookingParametersAdminUpdate,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        result = await BookingParametersService(database).update(payload.model_dump())
        await database.execute(
            text(
                """
                insert into tenant_log_entries(source,service,event,message,actor,details)
                values('admin','control-plane-support','booking_parameters_updated',
                       'Parâmetros da Agenda atualizados pelo Control Plane.',
                       :actor,cast(:details as jsonb))
                """
            ),
            {
                "actor": principal.email,
                "details": json.dumps({"tenant_id": tenant_id}),
            },
        )
        await database.commit()
        return success(result)
    return success({})


@router.get("/{tenant_id}/landing/{slug}")
async def tenant_landing_support(
    tenant_id: str,
    slug: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        return success(await LandingPageService(database).editor_state(slug))
    return success({})


@router.post("/{tenant_id}/landing/{slug}/draft")
async def save_tenant_landing_support(
    tenant_id: str,
    slug: str,
    payload: dict[str, Any] = Body(...),
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    TemplateContract.ensure_content("LANDING", payload, strict=True)
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        result = await LandingPageService(database).save_draft(
            slug,
            payload,
            created_by=None,
            label=f"Suporte Control Plane · {principal.email}",
        )
        return success(result)
    return success({})


@router.post("/{tenant_id}/landing/{slug}/publish")
async def publish_tenant_landing_support(
    tenant_id: str,
    slug: str,
    payload: LandingPublish,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        return success(
            await LandingPageService(database).publish(
                slug,
                version_id=payload.version_id,
            )
        )
    return success({})


@router.post("/{tenant_id}/landing/{slug}/apply-global-template")
async def apply_global_landing_template_support(
    tenant_id: str,
    slug: str,
    payload: GlobalTemplateApply,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    template = await GlobalTemplateService(platform).content(
        template_id=payload.template_id,
        version_number=payload.version_number,
        tenant_id=tenant_id,
    )
    if template["surface"] != "LANDING":
        from app.core.errors import APIError

        raise APIError("GLOBAL_TEMPLATE_SURFACE_MISMATCH", "Este modelo não é de Landing Page.", 422)
    TemplateContract.ensure_content(
        "LANDING",
        template["version"]["content"],
        strict=True,
    )
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        service = LandingPageService(database)
        draft = await service.save_draft(
            slug,
            template["version"]["content"],
            created_by=None,
            label=f"Modelo global: {template['name']} v{template['version']['version_number']}",
        )
        await database.execute(
            text("update landing_pages set template_key=:key where slug=:slug"),
            {
                "slug": slug,
                "key": f"global:{template['key']}@{template['version']['version_number']}",
            },
        )
        await database.commit()
        if payload.publish:
            await service.publish(slug, version_id=str(draft["version_id"]))
        return success({**draft, "global_template": template["key"]})
    return success({})


@router.get("/{tenant_id}/booking-page")
async def tenant_booking_page_support(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        rows = (
            await database.execute(
                text(
                    """
                    select key,value
                    from tenant_settings
                    where key like 'public_booking_%'
                       or key in ('booking_page_template_key','booking_page_template_version','booking_page_template_content')
                    order by key
                    """
                )
            )
        ).mappings().all()
        return success({str(row["key"]): row["value"] for row in rows})
    return success({})


@router.put("/{tenant_id}/booking-page")
async def update_tenant_booking_page_support(
    tenant_id: str,
    payload: BookingPageSettingsUpdate,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        for key, value in payload.values.items():
            if not key.startswith("public_booking_"):
                continue
            await database.execute(
                text(
                    """
                    insert into tenant_settings(key,value,updated_at)
                    values(:key,cast(:value as jsonb),now())
                    on conflict(key) do update set value=excluded.value,updated_at=now()
                    """
                ),
                {"key": key, "value": json.dumps(value, ensure_ascii=False)},
            )
        await database.commit()
        return success({"updated": True})
    return success({"updated": False})


@router.post("/{tenant_id}/booking-page/apply-global-template")
async def apply_global_booking_template_support(
    tenant_id: str,
    payload: GlobalTemplateApply,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    template = await GlobalTemplateService(platform).content(
        template_id=payload.template_id,
        version_number=payload.version_number,
        tenant_id=tenant_id,
    )
    if template["surface"] != "BOOKING":
        from app.core.errors import APIError

        raise APIError("GLOBAL_TEMPLATE_SURFACE_MISMATCH", "Este modelo não é de Página de Agendamento.", 422)
    TemplateContract.ensure_content(
        "BOOKING",
        template["version"]["content"],
        strict=True,
    )
    context = await _context(platform, tenant_id)
    async for database in tenant_session(context):
        values = {
            "booking_page_template_key": template["key"],
            "booking_page_template_version": int(template["version"]["version_number"]),
            "booking_page_template_content": template["version"]["content"],
        }
        for key, value in values.items():
            await database.execute(
                text(
                    """
                    insert into tenant_settings(key,value,updated_at)
                    values(:key,cast(:value as jsonb),now())
                    on conflict(key) do update set value=excluded.value,updated_at=now()
                    """
                ),
                {"key": key, "value": json.dumps(value, ensure_ascii=False)},
            )
        await database.commit()
        return success({"applied": True, "template": template["key"], "version": template["version"]["version_number"]})
    return success({"applied": False})


@router.get("/{tenant_id}/branding")
async def tenant_branding_support(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await _context(platform, tenant_id)
    return success(await BrandingService(platform).manifest_for_context(context))


@router.put("/{tenant_id}/branding")
async def update_tenant_branding_support(
    tenant_id: str,
    payload: dict[str, Any] = Body(...),
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    platform: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    tenant = await platform.execute(
        text("select slug from tenants where id=cast(:id as uuid)"),
        {"id": tenant_id},
    )
    slug = tenant.scalar_one()
    return success(
        await BrandingService(platform).save_profile(
            tenant_id,
            payload,
            tenant_name=str(slug),
        )
    )
