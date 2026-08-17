from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_platform_tenant_access,
    get_platform_session,
    require_platform_permission,
)
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.tenant_management_service import TenantManagementService

router = APIRouter()


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    timezone: str | None = Field(default=None, min_length=3, max_length=64)

    @model_validator(mode="after")
    def require_change(self) -> "TenantUpdateRequest":
        if self.name is None and self.timezone is None:
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


@router.get("/{tenant_id}")
async def tenant_management_snapshot(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await TenantManagementService(session).snapshot(tenant_id))


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
