from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_platform_user,
    get_current_tenant_user,
    get_platform_session,
    get_tenant_context,
    get_tenant_session,
    normalize_hostname,
    resolve_request_hostname,
)
from app.core.config import settings
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.auth_service import PlatformAuthService, TenantAuthService

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=1024)


def _request_meta(request: Request) -> tuple[str | None, str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = getattr(request.state, "correlation_id", None)
    return ip_address, user_agent, correlation_id


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    ip_address, user_agent, correlation_id = _request_meta(request)
    service = TenantAuthService(session, context)
    data = await service.login(
        str(payload.email), payload.password,
        user_agent=user_agent, ip_address=ip_address, correlation_id=correlation_id,
    )
    return success(data)


@router.post("/refresh")
async def refresh(
    payload: RefreshRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    return success(await TenantAuthService(session, context).refresh(payload.refresh_token))


@router.post("/logout")
async def logout(
    payload: RefreshRequest,
    _: AuthPrincipal = Depends(get_current_tenant_user),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    await TenantAuthService(session, context).logout(payload.refresh_token)
    return success({"logged_out": True})


@router.post("/logout-all")
async def logout_all(
    principal: AuthPrincipal = Depends(get_current_tenant_user),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    await TenantAuthService(session, context).logout_all(principal.user_id)
    return success({"logged_out": True, "all_sessions": True})


@router.post("/platform/login")
async def platform_login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_platform_session),
):
    if resolve_request_hostname(request) != normalize_hostname(settings.public_platform_domain):
        raise APIError("PLATFORM_DOMAIN_REQUIRED", "Login do control plane indisponível neste domínio.", 404)
    ip_address, user_agent, correlation_id = _request_meta(request)
    data = await PlatformAuthService(session).login(
        str(payload.email), payload.password,
        user_agent=user_agent, ip_address=ip_address, correlation_id=correlation_id,
    )
    return success(data)


@router.post("/platform/refresh")
async def platform_refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_platform_session),
):
    return success(await PlatformAuthService(session).refresh(payload.refresh_token))


@router.post("/platform/logout")
async def platform_logout(
    payload: RefreshRequest,
    _: AuthPrincipal = Depends(get_current_platform_user),
    session: AsyncSession = Depends(get_platform_session),
):
    await PlatformAuthService(session).logout(payload.refresh_token)
    return success({"logged_out": True})


@router.post("/platform/logout-all")
async def platform_logout_all(
    principal: AuthPrincipal = Depends(get_current_platform_user),
    session: AsyncSession = Depends(get_platform_session),
):
    await PlatformAuthService(session).logout_all(principal.user_id)
    return success({"logged_out": True, "all_sessions": True})
