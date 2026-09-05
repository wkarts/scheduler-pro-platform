from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.errors import APIError

IAM_PERMISSIONS = {
    "users.read": "Consultar usuários e grupos",
    "users.manage": "Administrar contas de usuários",
    "groups.manage": "Administrar grupos e permissões",
    "audit.read": "Consultar auditoria de acessos",
}


def assert_delegable(grants: set[str], authority: set[str]) -> None:
    if not grants.issubset(authority):
        raise APIError(
            "IAM_DELEGATION_DENIED", "Não é permitido gerenciar permissões superiores às suas.", 403
        )


async def lock_identity(session: AsyncSession | AsyncConnection) -> None:
    # Transaction-scoped and database-specific: serializes IAM writes, not requests/other tenants.
    await session.execute(
        text(
            "select pg_advisory_xact_lock(hashtext(current_database()),hashtext('tenant-identity'))"
        )
    )


async def permission_keys(
    session: AsyncSession, user_id: str, *, include_inactive: bool = False
) -> set[str]:
    active = "" if include_inactive else " and r.is_active"
    values = await session.execute(
        text(
            "select distinct p.key from user_roles ur join roles r on r.id=ur.role_id "
            "join role_permissions rp on rp.role_id=r.id join permissions p on p.id=rp.permission_id "
            f"where ur.user_id=cast(:id as uuid){active}"
        ),
        {"id": user_id},
    )
    return set(values.scalars())


async def revoke_access(
    session: AsyncSession | AsyncConnection, user_id: str, *, email_tokens: bool = True
) -> None:
    for table in ("user_sessions", "refresh_tokens"):
        await session.execute(
            text(
                f"update {table} set revoked_at=coalesce(revoked_at,now()) where user_id=cast(:id as uuid)"
            ),
            {"id": user_id},
        )
    await session.execute(
        text(
            "update service_api_tokens set revoked_at=coalesce(revoked_at,now()) where owner_id=cast(:id as uuid)"
        ),
        {"id": user_id},
    )
    await session.execute(
        text(
            "update password_reset_tokens set used_at=coalesce(used_at,now()) where user_id=cast(:id as uuid)"
        ),
        {"id": user_id},
    )
    if email_tokens:
        await session.execute(
            text(
                "update identity_email_tokens set used_at=coalesce(used_at,now()) where user_id=cast(:id as uuid)"
            ),
            {"id": user_id},
        )
