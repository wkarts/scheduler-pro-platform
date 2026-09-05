from collections.abc import AsyncIterator
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
import re
from typing import Any

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.db.session import platform_session, tenant_session
from app.integration_services.config import integration_settings

TOKEN_PATTERN = re.compile(r"^sp_(t|p)_([0-9a-f]{32})\.([A-Za-z0-9_-]{43})$")


@dataclass(frozen=True)
class IntegrationIdentity:
    principal: AuthPrincipal
    context: TenantContext | None
    token_id: str | None = None
    scopes: frozenset[str] = frozenset()
    capabilities: frozenset[str] = frozenset()
    control_plane_global: bool = False

    @property
    def platform(self) -> bool:
        return self.context is None

    @property
    def actor_key(self) -> str:
        return f"token:{self.token_id}" if self.token_id else f"user:{self.principal.user_id}"


@asynccontextmanager
async def integration_session(context: TenantContext | None) -> AsyncIterator[AsyncSession]:
    generator = platform_session() if context is None else tenant_session(context)
    async with aclosing(generator) as sessions:
        yield await anext(sessions)


async def resolve_scope(request: Request, platform: bool) -> TenantContext | None:
    from app.api.deps import get_tenant_context, resolve_request_hostname

    if not platform:
        return await get_tenant_context(request)
    hostname = resolve_request_hostname(request)
    allowed = {value.lower().rstrip(".") for value in settings.admin_platform_domains}
    allowed.add(settings.public_platform_domain.lower().rstrip("."))
    if hostname not in allowed:
        raise APIError("API_HOST_SCOPE_INVALID", "Utilize o domínio do Control Plane.", 403)
    return None


async def current_owner(
    session: AsyncSession,
    owner_id: str,
    context: TenantContext | None,
) -> AuthPrincipal:
    platform = context is None
    table = "platform_users" if platform else "users"
    extra = ", is_super_admin" if platform else ", verification_required, email_verified_at"
    row = (
        (
            await session.execute(
                text(
                    f"select id::text, email{extra} from {table} "
                    "where id=cast(:id as uuid) and is_active=true"
                ),
                {"id": owner_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None or (not platform and row["verification_required"] and not row["email_verified_at"]):
        raise APIError("API_TOKEN_INVALID", "Token inválido, revogado ou expirado.", 401)
    super_admin = platform and bool(row["is_super_admin"])
    if platform:
        permission_sql = (
            "select key from platform_permissions"
            if super_admin
            else "select distinct rp.permission_key from platform_role_permissions rp "
            "join platform_user_roles ur on ur.role_id=rp.role_id "
            "where ur.user_id=cast(:id as uuid)"
        )
        tenant_sql = (
            "select id::text from tenants"
            if super_admin
            else "select tenant_id::text from platform_user_tenants where user_id=cast(:id as uuid)"
        )
        tenant_ids = frozenset(
            str(v) for v in (await session.execute(text(tenant_sql), {"id": owner_id})).scalars()
        )
        roles: frozenset[str] = frozenset()
    else:
        permission_sql = (
            "select distinct p.key from permissions p "
            "join role_permissions rp on rp.permission_id=p.id "
            "join roles active_role on active_role.id=rp.role_id and active_role.is_active "
            "join user_roles ur on ur.role_id=rp.role_id where ur.user_id=cast(:id as uuid)"
        )
        tenant_ids = frozenset({context.tenant_id}) if context else frozenset()
        roles = frozenset(
            str(v)
            for v in (
                await session.execute(
                    text(
                        "select r.name from roles r join user_roles ur on ur.role_id=r.id and r.is_active "
                        "where ur.user_id=cast(:id as uuid)"
                    ),
                    {"id": owner_id},
                )
            ).scalars()
        )
    permissions = frozenset(
        str(v) for v in (await session.execute(text(permission_sql), {"id": owner_id})).scalars()
    )
    return AuthPrincipal(
        user_id=owner_id,
        email=row["email"],
        user_type="platform" if platform else "tenant",
        session_id="",
        tenant_id=context.tenant_id if context else None,
        permissions=permissions,
        roles=roles,
        tenant_ids=tenant_ids,
        is_super_admin=super_admin,
    )


async def authenticate_token(
    raw: str,
    context: TenantContext | None,
    required_scope: str,
) -> IntegrationIdentity:
    match = TOKEN_PATTERN.fullmatch(raw)
    expected = "p" if context is None else "t"
    if not integration_settings.api_enabled:
        raise APIError("API_SERVICES_DISABLED", "API Services está desativado.", 503)
    if match is None or match[1] != expected:
        raise APIError("API_TOKEN_INVALID", "Token inválido para este ambiente.", 401)
    async with integration_session(context) as session:
        row = (
            (
                await session.execute(
                    text(
                        "select id::text, owner_id::text, token_hash, scopes, permissions, roles, tenant_ids, global_scope, rate_limit "
                        "from service_api_tokens where id=cast(:id as uuid) "
                        "and revoked_at is null and (expires_at is null or expires_at>now())"
                    ),
                    {"id": match[2]},
                )
            )
            .mappings()
            .first()
        )
        if row is None or not compare_digest(
            str(row["token_hash"]), sha256(raw.encode()).hexdigest()
        ):
            raise APIError("API_TOKEN_INVALID", "Token inválido, revogado ou expirado.", 401)
        if required_scope not in row["scopes"]:
            raise APIError(
                "API_SCOPE_DENIED",
                "Token sem acesso a este recurso.",
                403,
                {"required_scope": required_scope},
            )
        owner = await current_owner(session, row["owner_id"], context)
        permissions = owner.permissions.intersection(row["permissions"])
        usage = (
            await session.execute(
                text(
                    "insert into service_api_usage(token_id,window_start,requests) "
                    "values(cast(:id as uuid),date_trunc('minute',now()),1) "
                    "on conflict(token_id) do update set "
                    "requests=case when service_api_usage.window_start=date_trunc('minute',now()) "
                    "then service_api_usage.requests+1 else 1 end, window_start=date_trunc('minute',now()) "
                    "returning requests"
                ),
                {"id": row["id"]},
            )
        ).scalar_one()
        await session.execute(
            text(
                "update service_api_tokens set last_used_at=now() where id=cast(:id as uuid) "
                "and (last_used_at is null or last_used_at<now()-interval '1 minute')"
            ),
            {"id": row["id"]},
        )
        await session.commit()
        if usage > row["rate_limit"]:
            raise APIError(
                "API_RATE_LIMIT",
                "Limite de requisições do token atingido.",
                429,
                {"retry_after": 60},
            )
        principal = AuthPrincipal(
            user_id=owner.user_id,
            email=owner.email,
            user_type=owner.user_type,
            session_id=row["id"],
            tenant_id=owner.tenant_id,
            permissions=frozenset(permissions),
            roles=owner.roles.intersection(row["roles"]),
            tenant_ids=owner.tenant_ids.intersection(row["tenant_ids"]),
        )
    return IntegrationIdentity(
        principal,
        context,
        row["id"],
        frozenset(row["scopes"]),
        await current_capabilities(context),
        bool(row["global_scope"]) and owner.is_super_admin,
    )


async def current_capabilities(context: TenantContext | None) -> frozenset[str]:
    if context is None:
        return frozenset()
    async with integration_session(None) as session:
        values = (
            await session.execute(
                text(
                    "select capability_key from tenant_capabilities "
                    "where tenant_id=cast(:id as uuid) and enabled=true"
                ),
                {"id": context.tenant_id},
            )
        ).scalars()
        return frozenset(str(value) for value in values)


async def authenticate_management(
    request: Request,
    context: TenantContext | None,
    raw: str,
) -> IntegrationIdentity:
    from app.api.deps import get_current_platform_user, get_current_tenant_user

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw)
    async with integration_session(context) as session:
        if context is None:
            principal = await get_current_platform_user(request, session, credentials)
        else:
            principal = await get_current_tenant_user(request, context, session, credentials)
    permission = "integrations.manage" if context is None else "tenant.manage"
    if permission not in principal.permissions and not principal.is_super_admin:
        raise APIError(
            "AUTH_PERMISSION_DENIED", "Permissão para gerenciar integrações obrigatória.", 403
        )
    return IntegrationIdentity(
        principal,
        context,
        capabilities=await current_capabilities(context),
        control_plane_global=principal.is_super_admin,
    )


async def audit(session: AsyncSession, actor: str, action: str, resource: str) -> None:
    await session.execute(
        text(
            "insert into service_integration_audit(actor_id,action,resource_id) "
            "values(cast(:actor as uuid),:action,cast(:resource as uuid))"
        ),
        {"actor": actor, "action": action, "resource": resource},
    )


def public_row(row: Any) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in dict(row).items()
        if key not in {"token_hash", "secret_ref", "authorization_ref", "response_sealed"}
    }
