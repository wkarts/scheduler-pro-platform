from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, require_platform_permission
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.html_template_contract import HtmlTemplateContract
from app.services.html_template_import_service import HtmlTemplateImportService

router = APIRouter()


class HtmlTemplateValidate(BaseModel):
    landing_html: str | None = None
    booking_html: str | None = None


class HtmlTemplateImport(BaseModel):
    landing_html: str | None = None
    booking_html: str | None = None
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    segment: str | None = Field(default=None, max_length=80)
    scope: Literal["GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"] = "INTERNAL"
    default_for_new_tenants: bool = False
    exclusive_tenant_id: str | None = None
    selected_tenant_ids: list[str] = Field(default_factory=list)
    publish: bool = False
    update_existing: bool = True


@router.get("/contract")
async def html_template_contract(
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> dict[str, Any]:
    return success(HtmlTemplateContract.descriptor())


@router.post("/validate")
async def validate_html_template_pair(
    payload: HtmlTemplateValidate,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
) -> dict[str, Any]:
    return success(
        HtmlTemplateContract.validate_pair(
            landing_html=payload.landing_html,
            booking_html=payload.booking_html,
        )
    )


@router.post("/import")
async def import_html_template_pair(
    payload: HtmlTemplateImport,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await HtmlTemplateImportService(session).import_pair(
            landing_html=payload.landing_html,
            booking_html=payload.booking_html,
            name=payload.name,
            description=payload.description,
            segment=payload.segment,
            actor=principal.email,
            scope=payload.scope,
            exclusive_tenant_id=payload.exclusive_tenant_id,
            selected_tenant_ids=payload.selected_tenant_ids,
            default_for_new_tenants=payload.default_for_new_tenants,
            publish=payload.publish,
            update_existing=payload.update_existing,
        )
    )
