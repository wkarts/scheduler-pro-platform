from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_platform_tenant_access,
    get_platform_session,
    require_platform_permission,
)
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.visual_builder_version_service import VisualBuilderVersionService

router = APIRouter()


class PlatformDefaultVersionUpdate(BaseModel):
    version: str = Field(min_length=5, max_length=20)


class TenantBuilderPolicyUpdate(BaseModel):
    allowed_versions: list[str] = Field(default_factory=list, max_length=20)
    default_version: str | None = Field(default=None, max_length=20)


@router.get("")
async def visual_builder_policy(
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await VisualBuilderVersionService(session).platform_policy())


@router.put("/default")
async def update_visual_builder_default(
    payload: PlatformDefaultVersionUpdate,
    _: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(
        await VisualBuilderVersionService(session).set_platform_default(payload.version)
    )


@router.get("/tenants/{tenant_id}")
async def tenant_visual_builder_policy(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await VisualBuilderVersionService(session).tenant_policy(tenant_id))


@router.put("/tenants/{tenant_id}")
async def update_tenant_visual_builder_policy(
    tenant_id: str,
    payload: TenantBuilderPolicyUpdate,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await VisualBuilderVersionService(session).set_tenant_policy(
            tenant_id,
            allowed_versions=payload.allowed_versions,
            default_version=payload.default_version,
        )
    )


@router.delete("/tenants/{tenant_id}")
async def reset_tenant_visual_builder_policy(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("templates.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await VisualBuilderVersionService(session).reset_tenant_policy(tenant_id))
