from collections.abc import AsyncIterator, Callable
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
    async for session in platform_session():
        yield session


async def get_tenant_context(request: Request) -> TenantContext:
    hostname = resolve_request_hostname(request)
    async for session in platform_session():
        resolver = TenantResolver(session)
        return await resolver.resolve(hostname)
    raise RuntimeError("platform session unavailable")


async def get_tenant_session(
    context: TenantContext = Depends(get_tenant_context),
) -> AsyncIterator[AsyncSession]:
    async for session in tenant_session(context):
        yield session


def _token(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError("AUTH_REQUIRED", "Autenticação obrigatória.", 401)
    return decode_access_token(credentials.credentials)


async def get_current_tenant_user(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthPrincipal:
    payload = _token(credentials)
    if payload.get("user_type") != "tenant":
        raise APIError("AUTH_SCOPE_INVALID", "Token não pertence ao tenant.", 403)
    context.assert_same_tenant(payload.get("tenant_id"))
    row = (
        await session.execute(
            text(
                """
                select u.id::text as id, u.email
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
                {"user_id": row["id"]},
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
                {"user_id": row["id"]},
            )
        ).scalars()
    )
    return AuthPrincipal(
        user_id=row["id"], email=row["email"], user_type="tenant",
        session_id=payload["sid"], tenant_id=context.tenant_id,
        permissions=frozenset(permissions), roles=frozenset(roles),
    )


async def get_current_user(
    principal: AuthPrincipal = Depends(get_current_tenant_user),
) -> AuthPrincipal:
    return principal


async def get_current_platform_user(
    session: AsyncSession = Depends(get_platform_session),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthPrincipal:
    payload = _token(credentials)
    if payload.get("user_type") != "platform":
        raise APIError("AUTH_SCOPE_INVALID", "Token não pertence ao control plane.", 403)
    row = (
        await session.execute(
            text(
                """
                select u.id::text as id, u.email, u.is_super_admin
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
    permissions = {"platform.manage", "builds.manage"} if row["is_super_admin"] else set()
    roles = {"super-admin"} if row["is_super_admin"] else set()
    return AuthPrincipal(
        user_id=row["id"], email=row["email"], user_type="platform",
        session_id=payload["sid"], tenant_id=None,
        permissions=frozenset(permissions), roles=frozenset(roles),
        is_super_admin=bool(row["is_super_admin"]),
    )


def require_permission(permission: str) -> Callable:
    async def dependency(principal: AuthPrincipal = Depends(get_current_user)) -> AuthPrincipal:
        if permission not in principal.permissions:
            raise APIError("AUTH_PERMISSION_DENIED", "Permissão insuficiente.", 403, {"permission": permission})
        return principal

    return dependency


def require_role(role: str) -> Callable:
    async def dependency(principal: AuthPrincipal = Depends(get_current_user)) -> AuthPrincipal:
        if role not in principal.roles:
            raise APIError("AUTH_ROLE_DENIED", "Perfil insuficiente.", 403, {"role": role})
        return principal

    return dependency


async def require_super_admin(
    principal: AuthPrincipal = Depends(get_current_platform_user),
) -> AuthPrincipal:
    if not principal.is_super_admin:
        raise APIError("AUTH_SUPER_ADMIN_REQUIRED", "Superadministrador obrigatório.", 403)
    return principal
