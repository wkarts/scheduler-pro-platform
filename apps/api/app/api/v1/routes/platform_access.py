from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_platform_user, get_platform_session, require_platform_permission
from app.core.security import AuthPrincipal
from app.core.responses import success
from app.services.platform_access_service import PlatformAccessService

router = APIRouter()


class RolePayload(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list)


class PlatformUserCreate(BaseModel):
    email: EmailStr
    display_name: str | None = Field(default=None, max_length=160)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    role_ids: list[str] = Field(default_factory=list)
    tenant_ids: list[str] = Field(default_factory=list)


class PlatformUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    is_active: bool = True
    role_ids: list[str] = Field(default_factory=list)
    tenant_ids: list[str] = Field(default_factory=list)


class PasswordResetPayload(BaseModel):
    password: str | None = Field(default=None, min_length=12, max_length=128)


class CapabilityPayload(BaseModel):
    enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/permissions")
async def permissions(
    _: AuthPrincipal = Depends(require_platform_permission("platform.roles.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).list_permissions())


@router.get("/roles")
async def roles(
    _: AuthPrincipal = Depends(require_platform_permission("platform.roles.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).list_roles())


@router.post("/roles")
async def create_role(
    payload: RolePayload,
    principal: AuthPrincipal = Depends(require_platform_permission("platform.roles.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).create_role(payload.name, payload.description, payload.permissions, principal.user_id))


@router.put("/roles/{role_id}")
async def update_role(
    role_id: str,
    payload: RolePayload,
    principal: AuthPrincipal = Depends(require_platform_permission("platform.roles.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).update_role(role_id, payload.name, payload.description, payload.permissions, principal.user_id))


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("platform.roles.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    await PlatformAccessService(session).delete_role(role_id, principal.user_id)
    return success({"deleted": True, "role_id": role_id})


@router.get("/users")
async def users(
    _: AuthPrincipal = Depends(require_platform_permission("platform.users.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).list_users())


@router.post("/users")
async def create_user(
    payload: PlatformUserCreate,
    principal: AuthPrincipal = Depends(require_platform_permission("platform.users.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).create_user(str(payload.email), payload.display_name, payload.password, payload.role_ids, payload.tenant_ids, principal.user_id))


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    payload: PlatformUserUpdate,
    principal: AuthPrincipal = Depends(require_platform_permission("platform.users.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).update_user(user_id, payload.display_name, payload.is_active, payload.role_ids, payload.tenant_ids, principal.user_id))


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    payload: PasswordResetPayload,
    principal: AuthPrincipal = Depends(require_platform_permission("platform.users.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).reset_password(user_id, payload.password, principal.user_id))


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("platform.users.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    await PlatformAccessService(session).delete_user(user_id, principal.user_id)
    return success({"deleted": True, "user_id": user_id})


@router.get("/tenants/{tenant_id}/capabilities")
async def tenant_capabilities(
    tenant_id: str,
    _: AuthPrincipal = Depends(require_platform_permission("tenant.capabilities.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).list_capabilities(tenant_id))


@router.put("/tenants/{tenant_id}/capabilities/{key}")
async def update_tenant_capability(
    tenant_id: str,
    key: str,
    payload: CapabilityPayload,
    principal: AuthPrincipal = Depends(require_platform_permission("tenant.capabilities.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAccessService(session).set_capability(tenant_id, key, payload.enabled, payload.config, principal.user_id))


@router.get("/me")
async def me(principal: AuthPrincipal = Depends(get_current_platform_user)) -> dict[str, Any]:
    return success({
        "id": principal.user_id,
        "email": principal.email,
        "roles": sorted(principal.roles),
        "permissions": sorted(principal.permissions),
        "tenant_ids": sorted(principal.tenant_ids),
        "is_super_admin": principal.is_super_admin,
    })
