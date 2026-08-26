from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, require_platform_permission
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.global_template_service import GlobalTemplateService

router = APIRouter()


class TemplateCreate(BaseModel):
    surface: Literal["LANDING", "BOOKING"]
    key: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    segment: str | None = Field(default=None, max_length=80)
    status: Literal["DRAFT", "PUBLISHED", "INACTIVE"] = "DRAFT"
    scope: Literal["GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"] = "INTERNAL"
    default_for_new_tenants: bool = False
    exclusive_tenant_id: str | None = None
    selected_tenant_ids: list[str] = Field(default_factory=list)
    content: dict[str, Any] | None = None
    changelog: str | None = None


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    segment: str | None = Field(default=None, max_length=80)
    status: Literal["DRAFT", "PUBLISHED", "INACTIVE"] | None = None
    scope: Literal["GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"] | None = None
    default_for_new_tenants: bool | None = None
    exclusive_tenant_id: str | None = None
    selected_tenant_ids: list[str] | None = None


class TemplateVersionCreate(BaseModel):
    content: dict[str, Any]
    changelog: str | None = None
    publish: bool = False


class TemplateDuplicate(BaseModel):
    key: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=180)


@router.get("")
async def list_global_templates(
    surface: Literal["LANDING", "BOOKING"] | None = Query(default=None),
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).list(
            surface=surface,
            include_internal=True,
        )
    )


@router.get("/available/{tenant_id}")
async def available_templates_for_tenant(
    tenant_id: str,
    surface: Literal["LANDING", "BOOKING"] | None = Query(default=None),
    _: AuthPrincipal = Depends(require_platform_permission("tenant.support.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).list(
            surface=surface,
            tenant_id=tenant_id,
        )
    )


@router.post("")
async def create_global_template(
    payload: TemplateCreate,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).create(
            payload.model_dump(),
            actor=principal.email,
        )
    )


@router.get("/{template_id}")
async def global_template_detail(
    template_id: str,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await GlobalTemplateService(session).get(template_id))


@router.put("/{template_id}")
async def update_global_template(
    template_id: str,
    payload: TemplateUpdate,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).update_metadata(
            template_id,
            payload.model_dump(exclude_unset=True),
            actor=principal.email,
        )
    )


@router.post("/{template_id}/versions")
async def create_global_template_version(
    template_id: str,
    payload: TemplateVersionCreate,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).create_version(
            template_id,
            payload.content,
            changelog=payload.changelog,
            actor=principal.email,
            publish=payload.publish,
        )
    )


@router.post("/{template_id}/versions/{version_number}/publish")
async def publish_global_template_version(
    template_id: str,
    version_number: int,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).publish_version(
            template_id,
            version_number,
            actor=principal.email,
        )
    )


@router.get("/{template_id}/versions/{version_number}/content")
async def global_template_version_content(
    template_id: str,
    version_number: int,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).content(
            template_id=template_id,
            version_number=version_number,
        )
    )


@router.post("/{template_id}/duplicate")
async def duplicate_global_template(
    template_id: str,
    payload: TemplateDuplicate = Body(...),
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await GlobalTemplateService(session).duplicate(
            template_id,
            new_key=payload.key,
            new_name=payload.name,
            actor=principal.email,
        )
    )
