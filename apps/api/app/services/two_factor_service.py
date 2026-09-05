from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.secrets import seal_secret, secret_resolver


@dataclass(frozen=True, slots=True)
class TwoFactorState:
    enabled: bool
    configured: bool
    mandatory: bool
    second_factor_verified: bool


class TwoFactorService:
    STEP_SECONDS = 30
    DIGITS = 6
    WINDOW = 1

    def __init__(
        self,
        session: AsyncSession,
        *,
        user_table: str,
        session_table: str,
        mandatory: bool,
        issuer: str = "Scheduler Pro",
    ) -> None:
        self.session = session
        self.user_table = user_table
        self.session_table = session_table
        self.mandatory = mandatory
        self.issuer = issuer

    @classmethod
    def platform(cls, session: AsyncSession) -> "TwoFactorService":
        return cls(
            session,
            user_table="platform_users",
            session_table="platform_user_sessions",
            mandatory=True,
            issuer="Scheduler Pro - Administração da Plataforma",
        )

    @classmethod
    def tenant(cls, session: AsyncSession) -> "TwoFactorService":
        return cls(
            session,
            user_table="users",
            session_table="user_sessions",
            mandatory=False,
            issuer="Scheduler Pro",
        )

    async def state(self, user_id: str, session_id: str) -> TwoFactorState:
        row = (
            await self.session.execute(
                text(
                    f"""
                    select u.two_factor_enabled,
                           u.two_factor_secret_ref is not null as configured,
                           s.second_factor_verified
                    from {self.user_table} u
                    join {self.session_table} s on s.user_id=u.id
                    where u.id=cast(:user_id as uuid)
                      and s.id=cast(:session_id as uuid)
                      and s.revoked_at is null
                      and s.expires_at > now()
                    limit 1
                    """
                ),
                {"user_id": user_id, "session_id": session_id},
            )
        ).mappings().first()
        if row is None:
            raise APIError("AUTH_SESSION_INVALID", "Sessão inválida ou expirada.", 401)
        return TwoFactorState(
            enabled=bool(row["two_factor_enabled"]),
            configured=bool(row["configured"]),
            mandatory=self.mandatory,
            second_factor_verified=bool(row["second_factor_verified"]),
        )

    async def begin_enrollment(
        self,
        *,
        user_id: str,
        email: str,
    ) -> dict[str, Any]:
        secret = self.generate_secret()
        await self.session.execute(
            text(
                f"""
                update {self.user_table}
                set two_factor_secret_ref=:secret_ref,
                    two_factor_enabled=false,
                    two_factor_confirmed_at=null,
                    two_factor_updated_at=now()
                where id=cast(:user_id as uuid)
                """
            ),
            {"user_id": user_id, "secret_ref": seal_secret(secret)},
        )
        await self.session.commit()
        uri = self.provisioning_uri(secret, email)
        return {
            "manual_key": secret,
            "otpauth_uri": uri,
            "qr_code": self.qr_data_uri(uri),
            "algorithm": "SHA1",
            "digits": self.DIGITS,
            "period": self.STEP_SECONDS,
        }

    async def confirm_enrollment(
        self,
        *,
        user_id: str,
        session_id: str,
        code: str,
    ) -> None:
        secret = await self._secret(user_id)
        if not self.verify_code(secret, code):
            raise APIError(
                "AUTH_SECOND_FACTOR_INVALID",
                "Código de verificação inválido.",
                422,
            )
        await self.session.execute(
            text(
                f"""
                update {self.user_table}
                set two_factor_enabled=true,
                    two_factor_confirmed_at=now(),
                    two_factor_updated_at=now()
                where id=cast(:user_id as uuid)
                """
            ),
            {"user_id": user_id},
        )
        await self._mark_session_verified(session_id)
        await self.session.commit()

    async def verify_session(
        self,
        *,
        user_id: str,
        session_id: str,
        code: str,
    ) -> None:
        state = await self.state(user_id, session_id)
        if not state.enabled:
            if self.mandatory:
                raise APIError(
                    "AUTH_SECOND_FACTOR_SETUP_REQUIRED",
                    "Configure a verificação em duas etapas para continuar.",
                    403,
                )
            raise APIError(
                "AUTH_SECOND_FACTOR_NOT_ENABLED",
                "A verificação em duas etapas não está ativada.",
                409,
            )
        secret = await self._secret(user_id)
        if not self.verify_code(secret, code):
            raise APIError(
                "AUTH_SECOND_FACTOR_INVALID",
                "Código de verificação inválido.",
                422,
            )
        await self._mark_session_verified(session_id)
        await self.session.commit()

    async def disable_tenant(
        self,
        *,
        user_id: str,
        code: str,
    ) -> None:
        if self.mandatory:
            raise APIError(
                "AUTH_SECOND_FACTOR_MANDATORY",
                "A verificação em duas etapas é obrigatória na Administração da Plataforma.",
                409,
            )
        secret = await self._secret(user_id)
        if not self.verify_code(secret, code):
            raise APIError(
                "AUTH_SECOND_FACTOR_INVALID",
                "Código de verificação inválido.",
                422,
            )
        await self.session.execute(
            text(
                f"""
                update {self.user_table}
                set two_factor_enabled=false,
                    two_factor_secret_ref=null,
                    two_factor_confirmed_at=null,
                    two_factor_updated_at=now()
                where id=cast(:user_id as uuid)
                """
            ),
            {"user_id": user_id},
        )
        await self.session.commit()

    async def _secret(self, user_id: str) -> str:
        reference = await self.session.scalar(
            text(
                f"select two_factor_secret_ref from {self.user_table} "
                "where id=cast(:user_id as uuid)"
            ),
            {"user_id": user_id},
        )
        if not reference:
            raise APIError(
                "AUTH_SECOND_FACTOR_SETUP_REQUIRED",
                "Configure a verificação em duas etapas para continuar.",
                403,
            )
        try:
            return secret_resolver.resolve(str(reference))
        except Exception as exc:
            raise APIError(
                "AUTH_SECOND_FACTOR_SECRET_INVALID",
                "Não foi possível validar a configuração de segurança.",
                500,
            ) from exc

    async def _mark_session_verified(self, session_id: str) -> None:
        verified_session_id = await self.session.scalar(
            text(
                f"""
                update {self.session_table}
                set second_factor_verified=true,
                    second_factor_verified_at=now(),
                    last_seen_at=now()
                where id=cast(:session_id as uuid)
                  and revoked_at is null
                  and expires_at > now()
                returning id::text
                """
            ),
            {"session_id": session_id},
        )
        if not verified_session_id:
            raise APIError("AUTH_SESSION_INVALID", "Sessão inválida ou expirada.", 401)
        if self.user_table == "users":
            await self.session.execute(text(
                "update users set last_login_at=now() where id=("
                "select user_id from user_sessions where id=cast(:id as uuid))"
            ), {"id": session_id})

    @staticmethod
    def generate_secret() -> str:
        return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")

    def provisioning_uri(self, secret: str, account: str) -> str:
        label = quote(f"{self.issuer}:{account}", safe="")
        issuer = quote(self.issuer, safe="")
        return (
            f"otpauth://totp/{label}?secret={secret}&issuer={issuer}"
            f"&algorithm=SHA1&digits={self.DIGITS}&period={self.STEP_SECONDS}"
        )

    @staticmethod
    def _decode_secret(secret: str) -> bytes:
        clean = secret.strip().replace(" ", "").upper()
        padding = "=" * ((8 - len(clean) % 8) % 8)
        return base64.b32decode(clean + padding, casefold=True)

    @classmethod
    def code_at(cls, secret: str, timestamp: int) -> str:
        counter = int(timestamp // cls.STEP_SECONDS)
        digest = hmac.new(
            cls._decode_secret(secret),
            struct.pack(">Q", counter),
            hashlib.sha1,
        ).digest()
        offset = digest[-1] & 0x0F
        value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
        return str(value % (10**cls.DIGITS)).zfill(cls.DIGITS)

    @classmethod
    def verify_code(cls, secret: str, code: str, *, now: int | None = None) -> bool:
        candidate = "".join(ch for ch in str(code or "") if ch.isdigit())
        if len(candidate) != cls.DIGITS:
            return False
        current = int(time.time() if now is None else now)
        for delta in range(-cls.WINDOW, cls.WINDOW + 1):
            expected = cls.code_at(secret, current + delta * cls.STEP_SECONDS)
            if hmac.compare_digest(expected, candidate):
                return True
        return False

    @staticmethod
    def qr_data_uri(uri: str) -> str:
        image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=6, border=2)
        buffer = io.BytesIO()
        image.save(buffer)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
