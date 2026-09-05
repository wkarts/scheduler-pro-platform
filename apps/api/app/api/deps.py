from contextlib import aclosing
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.security import AuthPrincipal, decode_access_token
from app.core.tenant_context import TenantContext
from app.db.session import platform_session, tenant_session
from app.services.tenant_resolver import TenantResolver

bearer_scheme = HTTPBearer(auto_error=False)


def normalize_hostname(value: str) -> str:
    candidate = value.strip().split(",", 1)[0].strip()
    if not candidate or "\x00" in candidate:
        raise APIError("HOST_INVALID", "Hostname inválido.", 400)
    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    hostname = parsed.hostname
    if not hostname:
        raise APIError("HOST_INVALID", "Hostname inválido.", 400)
    try:
        hostname = hostname.encode("idna").decode("ascii").rstrip(".").lower()
    except UnicodeError as exc:
        raise APIError("HOST_INVALID", "Hostname inválido.", 400) from exc
    if len(hostname) > 253:
        raise APIError("HOST_INVALID", "Hostname inválido.", 400)
    return hostname


def resolve_request_hostname(request: Request) -> str:
    client_host = request.client.host if request.client else None
    raw_host = request.headers.get("host") or settings.public_platform_domain
    if client_host in settings.trusted_proxy_hosts:
        forwarded = request.headers.get("x-forwarded-host")
        if forwarded:
            raw_host = forwarded
    return normalize_hostname(raw_host)


async def get_platform_session() -> AsyncIterator[AsyncSession]:
    async with aclosing(platform_session()) as _session_scope_48:
        async for session in _session_scope_48:
            yield session


async def get_tenant_context(request: Request) -> TenantContext:
    hostname = resolve_request_hostname(request)
    async with aclosing(platform_session()) as _session_scope_54:
        async for session in _session_scope_54:
            resolver = TenantResolver(session)
            return await resolver.resolve(hostname)
    raise RuntimeError("platform session unavailable")


async def get_tenant_session(
    context: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[AsyncSession]:
    async with aclosing(tenant_session(context)) as _session_scope_63:
        async for session in _session_scope_63:
            yield session


def _token(credentials: HTTPAuthorizationCredentials | None) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError("AUTH_REQUIRED", "Autenticação obrigatória.", 401)
    return decode_access_token(credentials.credentials)


async def _tenant_stage(
    context: TenantContext,
    session: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[AuthPrincipal, dict[str, Any]]:
    payload = _token(credentials)
    if payload.get("user_type") != "tenant":
        raise APIError("AUTH_SCOPE_INVALID", "Token não pertence à empresa.", 403)
    context.assert_same_tenant(payload.get("tenant_id"))
    row = (
        await session.execute(
            text(
                """
                select u.id::text as id, u.email,
                       u.two_factor_enabled,
                       (u.two_factor_secret_ref is not null) as two_factor_configured,
                       s.second_factor_verified
                from users u
                join user_sessions s on s.user_id=u.id
                where u.id=:user_id and s.id=:session_id
                  and u.is_active=true and s.revoked_at is null and s.expires_at>now()
                limit 1
                """
            ),
            {"user_id": payload["sub"], "session_id": payload["sid"]},
        )
    ).mappings().first()
    if row is None:
        raise APIError("AUTH_SESSION_INVALID", "Sessão inválida ou expirada.", 401)
    principal = AuthPrincipal(
        user_id=row["id"],
        email=row["email"],
        user_type="tenant",
        session_id=payload["sid"],
        tenant_id=context.tenant_id,
        permissions=frozenset(),
        roles=frozenset(),
        tenant_ids=frozenset({context.tenant_id}),
    )
    return principal, dict(row)


async def get_tenant_login_stage_user(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthPrincipal:
    principal, _ = await _tenant_stage(context, session, credentials)
    return principal


async def get_current_tenant_user(
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthPrincipal:
    service_principal = getattr(request.state, "integration_principal", None)
    if isinstance(service_principal, AuthPrincipal):
        if service_principal.user_type != "tenant" or service_principal.tenant_id != context.tenant_id:
            raise APIError("API_SCOPE_DENIED", "Token não pertence à empresa.", 403)
        return service_principal
    principal, row = await _tenant_stage(context, session, credentials)
    if bool(row["two_factor_enabled"]) and not bool(row["second_factor_verified"]):
        raise APIError(
            "AUTH_SECOND_FACTOR_REQUIRED",
            "Confirme a verificação em duas etapas para continuar.",
            403,
            {"mandatory": False, "setup_required": False},
        )
    permissions = set(
        (
            await session.execute(
                text(
                    """
                    select distinct p.key from permissions p
                    join role_permissions rp on rp.permission_id=p.id
                    join user_roles ur on ur.role_id=rp.role_id
                    where ur.user_id=:user_id
                    """
                ),
                {"user_id": principal.user_id},
            )
        ).scalars()
    )
    roles = set(
        (
            await session.execute(
                text(
                    """
                    select distinct r.name from roles r
                    join user_roles ur on ur.role_id=r.id
                    where ur.user_id=:user_id
                    """
                ),
                {"user_id": principal.user_id},
            )
        ).scalars()
    )
    return AuthPrincipal(
        user_id=principal.user_id,
        email=principal.email,
        user_type="tenant",
        session_id=principal.session_id,
        tenant_id=context.tenant_id,
        permissions=frozenset(permissions),
        roles=frozenset(roles),
        tenant_ids=frozenset({context.tenant_id}),
    )


async def get_current_user(
    principal: AuthPrincipal = Depends(get_current_tenant_user),
) -> AuthPrincipal:
    return principal


def require_tenant_capability(
    capability: str,
) -> Callable[..., Awaitable[None]]:
    async def dependency(
        context: TenantContext = Depends(get_tenant_context),
        session: AsyncSession = Depends(get_platform_session),
    ) -> None:
        enabled = (
            await session.execute(
                text(
                    """
                    select enabled
                    from tenant_capabilities
                    where tenant_id=cast(:tenant_id as uuid)
                      and capability_key=:capability
                    limit 1
                    """
                ),
                {"tenant_id": context.tenant_id, "capability": capability},
            )
        ).scalar_one_or_none()
        if enabled is not True:
            raise APIError(
                "TENANT_CAPABILITY_DISABLED",
                "Este recurso não está liberado para a empresa.",
                403,
                {"capability": capability},
            )

    return dependency


async def _platform_stage(
    session: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[AuthPrincipal, dict[str, Any]]:
    payload = _token(credentials)
    if payload.get("user_type") != "platform":
        raise APIError(
            "AUTH_SCOPE_INVALID",
            "Token não pertence à Administração da Plataforma.",
            403,
        )
    row = (
        await session.execute(
            text(
                """
                select u.id::text as id, u.email, u.is_super_admin,
                       u.two_factor_enabled,
                       (u.two_factor_secret_ref is not null) as two_factor_configured,
                       s.second_factor_verified
                from platform_users u
                join platform_user_sessions s on s.user_id=u.id
                where u.id=:user_id and s.id=:session_id
                  and u.is_active=true and s.revoked_at is null and s.expires_at>now()
                limit 1
                """
            ),
            {"user_id": payload["sub"], "session_id": payload["sid"]},
        )
    ).mappings().first()
    if row is None:
        raise APIError("AUTH_SESSION_INVALID", "Sessão inválida ou expirada.", 401)
    principal = AuthPrincipal(
        user_id=row["id"],
        email=row["email"],
        user_type="platform",
        session_id=payload["sid"],
        tenant_id=None,
        permissions=frozenset(),
        roles=frozenset({"super-admin"}) if bool(row["is_super_admin"]) else frozenset(),
        tenant_ids=frozenset(),
        is_super_admin=bool(row["is_super_admin"]),
    )
    return principal, dict(row)


async def get_platform_login_stage_user(
    session: AsyncSession = Depends(get_platform_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthPrincipal:
    principal, _ = await _platform_stage(session, credentials)
    return principal


async def get_current_platform_user(
    request: Request,
    session: AsyncSession = Depends(get_platform_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthPrincipal:
    service_principal = getattr(request.state, "integration_principal", None)
    if isinstance(service_principal, AuthPrincipal):
        if service_principal.user_type != "platform":
            raise APIError("API_SCOPE_DENIED", "Token não pertence ao Control Plane.", 403)
        return service_principal
    principal, row = await _platform_stage(session, credentials)
    if not bool(row["two_factor_enabled"]) or not bool(row["second_factor_verified"]):
        setup_required = not bool(row["two_factor_enabled"]) or not bool(
            row["two_factor_configured"]
        )
        raise APIError(
            "AUTH_SECOND_FACTOR_REQUIRED",
            (
                "Configure a verificação em duas etapas para continuar."
                if setup_required
                else "Informe o código da verificação em duas etapas para continuar."
            ),
            403,
            {"mandatory": True, "setup_required": setup_required},
        )

    is_super_admin = principal.is_super_admin
    if is_super_admin:
        permissions = set(
            (await session.execute(text("select key from platform_permissions"))).scalars()
        )
        roles = {"super-admin"}
        tenant_ids = set(
            (await session.execute(text("select id::text from tenants"))).scalars()
        )
    else:
        permissions = set(
            (
                await session.execute(
                    text(
                        """
                        select distinct rp.permission_key
                        from platform_role_permissions rp
                        join platform_user_roles ur on ur.role_id=rp.role_id
                        where ur.user_id=cast(:user_id as uuid)
                        """
                    ),
                    {"user_id": principal.user_id},
                )
            ).scalars()
        )
        roles = set(
            (
                await session.execute(
                    text(
                        """
                        select distinct r.name
                        from platform_roles r
                        join platform_user_roles ur on ur.role_id=r.id
                        where ur.user_id=cast(:user_id as uuid)
                        """
                    ),
                    {"user_id": principal.user_id},
                )
            ).scalars()
        )
        tenant_ids = set(
            (
                await session.execute(
                    text(
                        """
                        select tenant_id::text
                        from platform_user_tenants
                        where user_id=cast(:user_id as uuid)
                        """
                    ),
                    {"user_id": principal.user_id},
                )
            ).scalars()
        )

    return AuthPrincipal(
        user_id=principal.user_id,
        email=principal.email,
        user_type="platform",
        session_id=principal.session_id,
        tenant_id=None,
        permissions=frozenset(permissions),
        roles=frozenset(roles),
        tenant_ids=frozenset(tenant_ids),
        is_super_admin=is_super_admin,
    )


def require_permission(
    permission: str,
) -> Callable[[AuthPrincipal], Awaitable[AuthPrincipal]]:
    async def dependency(
        principal: AuthPrincipal = Depends(get_current_user),
    ) -> AuthPrincipal:
        if permission not in principal.permissions:
            raise APIError(
                "AUTH_PERMISSION_DENIED",
                "Permissão insuficiente.",
                403,
                {"permission": permission},
            )
        return principal

    return dependency


def require_platform_permission(
    permission: str,
) -> Callable[[AuthPrincipal], Awaitable[AuthPrincipal]]:
    async def dependency(
        principal: AuthPrincipal = Depends(get_current_platform_user),
    ) -> AuthPrincipal:
        if not principal.is_super_admin and permission not in principal.permissions:
            raise APIError(
                "AUTH_PERMISSION_DENIED",
                "Permissão administrativa insuficiente.",
                403,
                {"permission": permission},
            )
        return principal

    return dependency


def assert_platform_tenant_access(principal: AuthPrincipal, tenant_id: str) -> None:
    if principal.is_super_admin:
        return
    if tenant_id not in principal.tenant_ids:
        raise APIError(
            "AUTH_TENANT_SCOPE_DENIED",
            "Este administrador não possui acesso à empresa.",
            403,
            {"tenant_id": tenant_id},
        )


def require_role(
    role: str,
) -> Callable[[AuthPrincipal], Awaitable[AuthPrincipal]]:
    async def dependency(
        principal: AuthPrincipal = Depends(get_current_user),
    ) -> AuthPrincipal:
        if role not in principal.roles:
            raise APIError(
                "AUTH_ROLE_DENIED",
                "Perfil insuficiente.",
                403,
                {"role": role},
            )
        return principal

    return dependency


async def require_super_admin(
    principal: AuthPrincipal = Depends(get_current_platform_user),
) -> AuthPrincipal:
    if not principal.is_super_admin:
        raise APIError(
            "AUTH_SUPER_ADMIN_REQUIRED",
            "Superadministrador obrigatório.",
            403,
        )
    return principal
