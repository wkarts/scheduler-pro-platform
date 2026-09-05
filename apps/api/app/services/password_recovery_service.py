import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.security import hash_opaque_token, hash_password


class _PasswordRecoveryService:
    user_table: str
    reset_table: str
    session_table: str
    refresh_table: str
    audit_table: str

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _audit(
        self,
        user_id: str | None,
        action: str,
        result: str,
        *,
        ip_address: str | None,
        correlation_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await self.session.execute(
            text(
                f"""
                insert into {self.audit_table}(
                    user_id, action, result, ip_address, correlation_id, metadata
                ) values(
                    cast(:user_id as uuid), :action, :result, :ip_address,
                    :correlation_id, cast(:metadata as jsonb)
                )
                """
            ),
            {
                "user_id": user_id,
                "action": action,
                "result": result,
                "ip_address": (ip_address or "")[:64] or None,
                "correlation_id": (correlation_id or "")[:120] or None,
                "metadata": json.dumps(metadata or {}, separators=(",", ":")),
            },
        )

    async def create_reset_token(
        self,
        email: str,
        *,
        ip_address: str | None,
        correlation_id: str | None,
    ) -> tuple[str, str] | None:
        if self.user_table == "users":
            from app.identity.policy import lock_identity
            await lock_identity(self.session)
        normalized = email.strip().lower()
        row = (
            await self.session.execute(
                text(
                    f"""
                    select id::text as id, email
                    from {self.user_table}
                    where lower(email)=:email and is_active=true
                    limit 1
                    """
                ),
                {"email": normalized},
            )
        ).mappings().first()

        # A resposta HTTP do endpoint é sempre a mesma para evitar enumeração de usuários.
        if row is None:
            await self._audit(
                None,
                "auth.password_reset.request",
                "IGNORED",
                ip_address=ip_address,
                correlation_id=correlation_id,
                metadata={"reason": "unknown_or_inactive_user"},
            )
            await self.session.commit()
            return None

        now = datetime.now(UTC)
        await self.session.execute(
            text(
                f"""
                update {self.reset_table}
                set used_at=coalesce(used_at, :now)
                where user_id=cast(:user_id as uuid) and used_at is null
                """
            ),
            {"user_id": row["id"], "now": now},
        )
        plain_token = secrets.token_urlsafe(32)
        token_hash = hash_opaque_token(plain_token)
        expires_at = now + timedelta(minutes=settings.password_reset_ttl_minutes)
        await self.session.execute(
            text(
                f"""
                insert into {self.reset_table}(user_id, token_hash, expires_at)
                values(cast(:user_id as uuid), :token_hash, :expires_at)
                """
            ),
            {
                "user_id": row["id"],
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )
        await self._audit(
            row["id"],
            "auth.password_reset.request",
            "SUCCESS",
            ip_address=ip_address,
            correlation_id=correlation_id,
            metadata={"expires_at": expires_at.isoformat()},
        )
        await self.session.commit()
        return str(row["email"]), plain_token

    async def complete_reset(
        self,
        raw_token: str,
        new_password: str,
        *,
        ip_address: str | None,
        correlation_id: str | None,
    ) -> None:
        if self.user_table == "users":
            from app.identity.policy import lock_identity
            await lock_identity(self.session)
        if not settings.password_reset_min_length <= len(new_password) <= 512:
            raise APIError(
                "PASSWORD_TOO_SHORT",
                f"A nova senha deve possuir pelo menos {settings.password_reset_min_length} caracteres.",
                422,
            )
        token_hash = hash_opaque_token(raw_token)
        now = datetime.now(UTC)
        row = (
            await self.session.execute(
                text(
                    f"""
                    select pr.id::text as reset_id,
                           pr.user_id::text as user_id,
                           pr.expires_at,
                           pr.used_at,
                           u.is_active
                    from {self.reset_table} pr
                    join {self.user_table} u on u.id=pr.user_id
                    where pr.token_hash=:token_hash
                    limit 1
                    for update of pr
                    """
                ),
                {"token_hash": token_hash},
            )
        ).mappings().first()
        if (
            row is None
            or row["used_at"] is not None
            or row["expires_at"] <= now
            or not row["is_active"]
        ):
            await self.session.rollback()
            raise APIError(
                "PASSWORD_RESET_INVALID",
                "Token de recuperação inválido ou expirado.",
                400,
            )

        await self.session.execute(
            text(
                f"""
                update {self.user_table}
                set password_hash=:password_hash,
                    failed_login_attempts=0,
                    locked_until=null,
                    updated_at=now()
                where id=cast(:user_id as uuid)
                """
            ),
            {
                "user_id": row["user_id"],
                "password_hash": hash_password(new_password),
            },
        )
        await self.session.execute(
            text(
                f"""
                update {self.session_table}
                set revoked_at=coalesce(revoked_at, now())
                where user_id=cast(:user_id as uuid)
                """
            ),
            {"user_id": row["user_id"]},
        )
        await self.session.execute(
            text(
                f"""
                update {self.refresh_table}
                set revoked_at=coalesce(revoked_at, now())
                where user_id=cast(:user_id as uuid)
                """
            ),
            {"user_id": row["user_id"]},
        )
        await self.session.execute(
            text(
                f"""
                update {self.reset_table}
                set used_at=coalesce(used_at, now())
                where user_id=cast(:user_id as uuid) and used_at is null
                """
            ),
            {"user_id": row["user_id"]},
        )
        if self.user_table == "users":
            from app.identity.policy import revoke_access
            await revoke_access(self.session, row["user_id"])
            await self.session.execute(text("update users set email_verified_at=coalesce(email_verified_at,now()),verification_required=false where id=cast(:id as uuid)"), {"id": row["user_id"]})
        await self._audit(
            row["user_id"],
            "auth.password_reset.complete",
            "SUCCESS",
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
        await self.session.commit()


class TenantPasswordRecoveryService(_PasswordRecoveryService):
    user_table = "users"
    reset_table = "password_reset_tokens"
    session_table = "user_sessions"
    refresh_table = "refresh_tokens"
    audit_table = "audit_logs"


class PlatformPasswordRecoveryService(_PasswordRecoveryService):
    user_table = "platform_users"
    reset_table = "platform_password_reset_tokens"
    session_table = "platform_user_sessions"
    refresh_table = "platform_refresh_tokens"
    audit_table = "platform_audit_logs"
