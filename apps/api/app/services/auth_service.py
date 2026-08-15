import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from app.core.tenant_context import TenantContext

_DUMMY_HASH = hash_password("scheduler-pro-dummy-password-not-a-user")


class _BaseAuthService:
    user_table: str
    session_table: str
    refresh_table: str
    audit_table: str
    user_type: str

    def __init__(self, session: AsyncSession, tenant_id: str | None = None) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def _audit(
        self,
        user_id: str | None,
        action: str,
        result: str,
        ip_address: str | None,
        correlation_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.session.execute(
            text(
                f"""
                insert into {self.audit_table}(
                    user_id, action, result, ip_address, correlation_id, metadata
                )
                values(
                    :user_id, :action, :result, :ip, :correlation_id, cast(:metadata as jsonb)
                )
                """
            ),
            {
                "user_id": user_id,
                "action": action,
                "result": result,
                "ip": ip_address,
                "correlation_id": correlation_id,
                "metadata": json.dumps(metadata or {}, separators=(",", ":")),
            },
        )

    async def _permissions(
        self,
        user_id: str,
        is_super_admin: bool = False,
    ) -> tuple[list[str], list[str]]:
        if self.user_type == "platform":
            permissions = ["platform.manage", "builds.manage"] if is_super_admin else []
            return permissions, ["super-admin"] if is_super_admin else []
        permission_rows = await self.session.execute(
            text(
                """
                select distinct p.key
                from permissions p
                join role_permissions rp on rp.permission_id = p.id
                join user_roles ur on ur.role_id = rp.role_id
                where ur.user_id = :user_id
                order by p.key
                """
            ),
            {"user_id": user_id},
        )
        role_rows = await self.session.execute(
            text(
                """
                select distinct r.name
                from roles r
                join user_roles ur on ur.role_id = r.id
                where ur.user_id = :user_id
                order by r.name
                """
            ),
            {"user_id": user_id},
        )
        return list(permission_rows.scalars()), list(role_rows.scalars())

    async def _lookup_user(self, email: str) -> RowMapping | None:
        extra = ", is_super_admin" if self.user_type == "platform" else ""
        result = await self.session.execute(
            text(
                f"""
                select id::text as id, email, password_hash, is_active,
                       failed_login_attempts, locked_until {extra}
                from {self.user_table}
                where lower(email) = :email
                limit 1
                """
            ),
            {"email": email.lower()},
        )
        return result.mappings().first()

    async def login(
        self,
        email: str,
        password: str,
        *,
        user_agent: str | None,
        ip_address: str | None,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        user = await self._lookup_user(email)
        if user is None:
            verify_password(password, _DUMMY_HASH)
            await self._audit(None, "auth.login", "DENIED", ip_address, correlation_id)
            await self.session.commit()
            raise APIError("AUTH_INVALID_CREDENTIALS", "E-mail ou senha inválidos.", 401)

        user_id = user["id"]
        locked_until = user["locked_until"]
        if not user["is_active"] or (locked_until is not None and locked_until > now):
            verify_password(password, _DUMMY_HASH)
            await self._audit(user_id, "auth.login", "DENIED", ip_address, correlation_id)
            await self.session.commit()
            raise APIError("AUTH_INVALID_CREDENTIALS", "E-mail ou senha inválidos.", 401)

        if not verify_password(password, user["password_hash"]):
            attempts = int(user["failed_login_attempts"] or 0) + 1
            new_lock = None
            if attempts >= settings.max_login_attempts:
                new_lock = now + timedelta(minutes=settings.login_lock_minutes)
                attempts = 0
            await self.session.execute(
                text(
                    f"""
                    update {self.user_table}
                    set failed_login_attempts=:attempts,
                        locked_until=:locked_until,
                        updated_at=now()
                    where id=:user_id
                    """
                ),
                {
                    "attempts": attempts,
                    "locked_until": new_lock,
                    "user_id": user_id,
                },
            )
            await self._audit(user_id, "auth.login", "DENIED", ip_address, correlation_id)
            await self.session.commit()
            raise APIError("AUTH_INVALID_CREDENTIALS", "E-mail ou senha inválidos.", 401)

        await self.session.execute(
            text(
                f"""
                update {self.user_table}
                set failed_login_attempts=0, locked_until=null, updated_at=now()
                where id=:user_id
                """
            ),
            {"user_id": user_id},
        )
        is_super_admin = bool(user.get("is_super_admin", False))
        permissions, roles = await self._permissions(user_id, is_super_admin)
        expires_at = now + timedelta(days=settings.refresh_token_days)
        session_id = (
            await self.session.execute(
                text(
                    f"""
                    insert into {self.session_table}(
                        user_id, expires_at, user_agent, ip_address
                    )
                    values(:user_id, :expires_at, :user_agent, :ip_address)
                    returning id::text
                    """
                ),
                {
                    "user_id": user_id,
                    "expires_at": expires_at,
                    "user_agent": (user_agent or "")[:1000] or None,
                    "ip_address": (ip_address or "")[:64] or None,
                },
            )
        ).scalar_one()
        refresh_token, refresh_hash = create_refresh_token()
        await self.session.execute(
            text(
                f"""
                insert into {self.refresh_table}(
                    session_id, user_id, token_hash, expires_at
                )
                values(:session_id, :user_id, :token_hash, :expires_at)
                """
            ),
            {
                "session_id": session_id,
                "user_id": user_id,
                "token_hash": refresh_hash,
                "expires_at": expires_at,
            },
        )
        await self._audit(user_id, "auth.login", "SUCCESS", ip_address, correlation_id)
        await self.session.commit()

        access_token = create_access_token(
            user_id,
            self.tenant_id,
            permissions,
            session_id=session_id,
            user_type=self.user_type,
            is_super_admin=is_super_admin,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_minutes * 60,
            "user": {
                "id": user_id,
                "email": user["email"],
                "permissions": permissions,
                "roles": roles,
                "is_super_admin": is_super_admin,
            },
        }

    async def refresh(self, raw_refresh_token: str) -> dict[str, Any]:
        token_hash = hash_opaque_token(raw_refresh_token)
        extra = ", u.is_super_admin" if self.user_type == "platform" else ""
        result = await self.session.execute(
            text(
                f"""
                select rt.id::text as token_id,
                       rt.session_id::text as session_id,
                       rt.user_id::text as user_id,
                       rt.expires_at,
                       rt.revoked_at,
                       s.revoked_at as session_revoked_at,
                       s.expires_at as session_expires_at,
                       u.email,
                       u.is_active {extra}
                from {self.refresh_table} rt
                join {self.session_table} s on s.id=rt.session_id
                join {self.user_table} u on u.id=rt.user_id
                where rt.token_hash=:token_hash
                limit 1
                """
            ),
            {"token_hash": token_hash},
        )
        row = result.mappings().first()
        now = datetime.now(UTC)
        if row is None:
            raise APIError("AUTH_REFRESH_INVALID", "Refresh token inválido ou expirado.", 401)
        if row["revoked_at"] is not None:
            await self.session.execute(
                text(
                    f"update {self.session_table} "
                    "set revoked_at=coalesce(revoked_at, now()) "
                    "where id=:session_id"
                ),
                {"session_id": row["session_id"]},
            )
            await self.session.execute(
                text(
                    f"update {self.refresh_table} "
                    "set revoked_at=coalesce(revoked_at, now()) "
                    "where session_id=:session_id"
                ),
                {"session_id": row["session_id"]},
            )
            await self.session.commit()
            raise APIError(
                "AUTH_REFRESH_REUSED",
                "Sessão revogada por reutilização de refresh token.",
                401,
            )
        if (
            row["expires_at"] <= now
            or row["session_expires_at"] <= now
            or row["session_revoked_at"] is not None
            or not row["is_active"]
        ):
            raise APIError("AUTH_REFRESH_INVALID", "Refresh token inválido ou expirado.", 401)

        user_id = row["user_id"]
        is_super_admin = bool(row.get("is_super_admin", False))
        permissions, roles = await self._permissions(user_id, is_super_admin)
        replacement, replacement_hash = create_refresh_token()
        replacement_id = (
            await self.session.execute(
                text(
                    f"""
                    insert into {self.refresh_table}(
                        session_id, user_id, token_hash, expires_at
                    )
                    values(:session_id, :user_id, :token_hash, :expires_at)
                    returning id::text
                    """
                ),
                {
                    "session_id": row["session_id"],
                    "user_id": user_id,
                    "token_hash": replacement_hash,
                    "expires_at": row["session_expires_at"],
                },
            )
        ).scalar_one()
        await self.session.execute(
            text(
                f"""
                update {self.refresh_table}
                set revoked_at=now(), replaced_by_token_id=:replacement_id
                where id=:token_id
                """
            ),
            {"replacement_id": replacement_id, "token_id": row["token_id"]},
        )
        await self.session.execute(
            text(
                f"update {self.session_table} "
                "set last_seen_at=now() where id=:session_id"
            ),
            {"session_id": row["session_id"]},
        )
        await self.session.commit()
        access_token = create_access_token(
            user_id,
            self.tenant_id,
            permissions,
            session_id=row["session_id"],
            user_type=self.user_type,
            is_super_admin=is_super_admin,
        )
        return {
            "access_token": access_token,
            "refresh_token": replacement,
            "token_type": "bearer",
            "expires_in": settings.access_token_minutes * 60,
            "user": {
                "id": user_id,
                "email": row["email"],
                "permissions": permissions,
                "roles": roles,
                "is_super_admin": is_super_admin,
            },
        }

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_opaque_token(raw_refresh_token)
        token = (
            await self.session.execute(
                text(
                    f"select session_id::text from {self.refresh_table} "
                    "where token_hash=:token_hash"
                ),
                {"token_hash": token_hash},
            )
        ).scalar_one_or_none()
        if token is not None:
            await self.session.execute(
                text(
                    f"update {self.refresh_table} "
                    "set revoked_at=coalesce(revoked_at, now()) "
                    "where session_id=:session_id"
                ),
                {"session_id": token},
            )
            await self.session.execute(
                text(
                    f"update {self.session_table} "
                    "set revoked_at=coalesce(revoked_at, now()) "
                    "where id=:session_id"
                ),
                {"session_id": token},
            )
            await self.session.commit()

    async def logout_all(self, user_id: str) -> None:
        await self.session.execute(
            text(
                f"update {self.session_table} "
                "set revoked_at=coalesce(revoked_at, now()) where user_id=:user_id"
            ),
            {"user_id": user_id},
        )
        await self.session.execute(
            text(
                f"update {self.refresh_table} "
                "set revoked_at=coalesce(revoked_at, now()) where user_id=:user_id"
            ),
            {"user_id": user_id},
        )
        await self.session.commit()


class TenantAuthService(_BaseAuthService):
    user_table = "users"
    session_table = "user_sessions"
    refresh_table = "refresh_tokens"
    audit_table = "audit_logs"
    user_type = "tenant"

    def __init__(self, session: AsyncSession, context: TenantContext) -> None:
        super().__init__(session, tenant_id=context.tenant_id)


class PlatformAuthService(_BaseAuthService):
    user_table = "platform_users"
    session_table = "platform_user_sessions"
    refresh_table = "platform_refresh_tokens"
    audit_table = "platform_audit_logs"
    user_type = "platform"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, tenant_id=None)
