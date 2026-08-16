from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any, cast

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.errors import APIError

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    user_id: str
    email: str
    user_type: str
    session_id: str
    tenant_id: str | None
    permissions: frozenset[str]
    roles: frozenset[str] = frozenset()
    tenant_ids: frozenset[str] = frozenset()
    is_super_admin: bool = False


def hash_password(password: str) -> str:
    return cast(str, pwd_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bool(pwd_context.verify(password, password_hash))
    except (TypeError, ValueError):
        return False


def hash_opaque_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token() -> tuple[str, str]:
    raw = token_urlsafe(48)
    return raw, hash_opaque_token(raw)


def create_access_token(
    subject: str,
    tenant_id: str | None,
    permissions: list[str],
    expires_minutes: int | None = None,
    *,
    session_id: str | None = None,
    user_type: str = "tenant",
    is_super_admin: bool = False,
) -> str:
    now = datetime.now(UTC)
    expiration = now + timedelta(minutes=expires_minutes or settings.access_token_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "sid": session_id,
        "tenant_id": tenant_id,
        "permissions": permissions,
        "user_type": user_type,
        "is_super_admin": is_super_admin,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp()),
    }
    return cast(str, jwt.encode(payload, settings.app_secret_key, algorithm="HS256"))


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = cast(
            dict[str, Any],
            jwt.decode(token, settings.app_secret_key, algorithms=["HS256"]),
        )
    except JWTError as exc:
        raise APIError("AUTH_TOKEN_INVALID", "Token de acesso inválido ou expirado.", 401) from exc
    if payload.get("type") != "access" or not payload.get("sub") or not payload.get("sid"):
        raise APIError("AUTH_TOKEN_INVALID", "Token de acesso inválido ou expirado.", 401)
    return payload
