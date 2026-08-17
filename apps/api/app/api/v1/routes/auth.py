import asyncio
from typing import Any
from urllib.parse import quote

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
from app.services.auth_service import TenantAuthService
from app.services.mail_service import mail_delivery
from app.services.password_recovery_service import (
    PlatformPasswordRecoveryService,
    TenantPasswordRecoveryService,
)
from app.services.platform_auth_service import PlatformAuthService

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=1024)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=1024)
    new_password: str = Field(min_length=8, max_length=512)


class MailTestRequest(BaseModel):
    recipient: EmailStr


def _request_meta(request: Request) -> tuple[str | None, str | None, str | None]:
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = getattr(request.state, "correlation_id", None)
    return ip_address, user_agent, correlation_id


def _is_platform_login_host(hostname: str) -> bool:
    allowed_hosts = {normalize_hostname(settings.public_platform_domain)}
    allowed_hosts.update(normalize_hostname(host) for host in settings.admin_platform_domains)
    return hostname in allowed_hosts or hostname.startswith("admin.")


def _external_origin(request: Request, hostname: str) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    scheme = forwarded_proto or request.url.scheme or "https"
    if settings.app_env != "development" or scheme not in {"http", "https"}:
        scheme = "https"
    return f"{scheme}://{normalize_hostname(hostname)}"


def _accepted_reset_response() -> dict[str, Any]:
    return success(
        {
            "accepted": True,
            "message": "Se o e-mail informado estiver cadastrado e ativo, enviaremos as instruções de recuperação.",
        }
    )


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    ip_address, user_agent, correlation_id = _request_meta(request)
    service = TenantAuthService(session, context)
    data = await service.login(
        str(payload.email),
        payload.password,
        user_agent=user_agent,
        ip_address=ip_address,
        correlation_id=correlation_id,
    )
    return success(data)


@router.post("/password/forgot")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    ip_address, _, correlation_id = _request_meta(request)
    created = await TenantPasswordRecoveryService(session).create_reset_token(
        str(payload.email),
        ip_address=ip_address,
        correlation_id=correlation_id,
    )
    if created is not None:
        recipient, raw_token = created
        reset_url = (
            f"{_external_origin(request, context.hostname)}/"
            f"?reset-token={quote(raw_token, safe='')}&reset-scope=tenant"
        )
        await asyncio.to_thread(
            mail_delivery.send_password_reset,
            recipient=recipient,
            reset_url=reset_url,
            platform_access=False,
        )
    return _accepted_reset_response()


@router.post("/password/reset")
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    ip_address, _, correlation_id = _request_meta(request)
    await TenantPasswordRecoveryService(session).complete_reset(
        payload.token,
        payload.new_password,
        ip_address=ip_address,
        correlation_id=correlation_id,
    )
    return success({"password_reset": True, "message": "Senha redefinida. Entre novamente."})


@router.post("/refresh")
async def refresh(
    payload: RefreshRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await TenantAuthService(session, context).refresh(payload.refresh_token))


@router.post("/logout")
async def logout(
    payload: RefreshRequest,
    _: AuthPrincipal = Depends(get_current_tenant_user),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    await TenantAuthService(session, context).logout(payload.refresh_token)
    return success({"logged_out": True})


@router.post("/logout-all")
async def logout_all(
    principal: AuthPrincipal = Depends(get_current_tenant_user),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    await TenantAuthService(session, context).logout_all(principal.user_id)
    return success({"logged_out": True, "all_sessions": True})


@router.post("/platform/login")
async def platform_login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    if not _is_platform_login_host(resolve_request_hostname(request)):
        raise APIError(
            "PLATFORM_DOMAIN_REQUIRED",
            "Login administrativo indisponível neste domínio.",
            404,
        )
    ip_address, user_agent, correlation_id = _request_meta(request)
    data = await PlatformAuthService(session).login(
        str(payload.email),
        payload.password,
        user_agent=user_agent,
        ip_address=ip_address,
        correlation_id=correlation_id,
    )
    return success(data)


@router.post("/platform/password/forgot")
async def platform_forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    hostname = resolve_request_hostname(request)
    if not _is_platform_login_host(hostname):
        raise APIError(
            "PLATFORM_DOMAIN_REQUIRED",
            "Recuperação administrativa indisponível neste domínio.",
            404,
        )
    ip_address, _, correlation_id = _request_meta(request)
    created = await PlatformPasswordRecoveryService(session).create_reset_token(
        str(payload.email),
        ip_address=ip_address,
        correlation_id=correlation_id,
    )
    if created is not None:
        recipient, raw_token = created
        reset_url = (
            f"{_external_origin(request, hostname)}/"
            f"?reset-token={quote(raw_token, safe='')}&reset-scope=platform"
        )
        await asyncio.to_thread(
            mail_delivery.send_password_reset,
            recipient=recipient,
            reset_url=reset_url,
            platform_access=True,
        )
    return _accepted_reset_response()


@router.post("/platform/password/reset")
async def platform_reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    hostname = resolve_request_hostname(request)
    if not _is_platform_login_host(hostname):
        raise APIError(
            "PLATFORM_DOMAIN_REQUIRED",
            "Recuperação administrativa indisponível neste domínio.",
            404,
        )
    ip_address, _, correlation_id = _request_meta(request)
    await PlatformPasswordRecoveryService(session).complete_reset(
        payload.token,
        payload.new_password,
        ip_address=ip_address,
        correlation_id=correlation_id,
    )
    return success({"password_reset": True, "message": "Senha redefinida. Entre novamente."})


@router.get("/platform/mail/status")
async def platform_mail_status(
    _: AuthPrincipal = Depends(get_current_platform_user),
) -> dict[str, Any]:
    return success(mail_delivery.status())


@router.post("/platform/mail/test")
async def platform_mail_test(
    payload: MailTestRequest,
    _: AuthPrincipal = Depends(get_current_platform_user),
) -> dict[str, Any]:
    result = await asyncio.to_thread(
        mail_delivery.send_test_message,
        recipient=str(payload.recipient),
    )
    if not result.delivered:
        raise APIError(
            result.error_code or "SMTP_DELIVERY_FAILED",
            result.message or "Falha ao enviar mensagem SMTP.",
            503,
        )
    return success({"delivered": True})


@router.post("/platform/refresh")
async def platform_refresh(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await PlatformAuthService(session).refresh(payload.refresh_token))


@router.post("/platform/logout")
async def platform_logout(
    payload: RefreshRequest,
    _: AuthPrincipal = Depends(get_current_platform_user),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    await PlatformAuthService(session).logout(payload.refresh_token)
    return success({"logged_out": True})


@router.post("/platform/logout-all")
async def platform_logout_all(
    principal: AuthPrincipal = Depends(get_current_platform_user),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    await PlatformAuthService(session).logout_all(principal.user_id)
    return success({"logged_out": True, "all_sessions": True})
