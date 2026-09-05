"""Durable at-most-one dispatch, encrypted replay, fail-closed ambiguous outcomes.

Existing business services own their commits. Therefore this ledger deliberately
never retries an abandoned reservation: a crash after a business commit is an
UNKNOWN outcome, not permission to run the mutation twice.
"""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.core.errors import APIError
from app.core.secrets import seal_secret, secret_resolver
from app.integration_services.auth import IntegrationIdentity, integration_session
from app.integration_services.config import integration_settings as config

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")


@dataclass(frozen=True)
class Reservation:
    id: str
    replay: dict[str, Any] | None = None


def request_fingerprint(method: str, path: str, query: str, content_type: str, body: bytes) -> str:
    metadata = json.dumps([method, path, query, content_type], separators=(",", ":")).encode()
    return sha256(metadata + b"\0" + body).hexdigest()


def authorization_snapshot(identity: IntegrationIdentity) -> dict[str, list[str]]:
    return {
        "permissions": sorted(identity.principal.permissions),
        "roles": sorted(identity.principal.roles),
        "tenant_ids": sorted(identity.principal.tenant_ids),
        "capabilities": sorted(identity.capabilities),
        "global_access": ["platform"] if identity.control_plane_global else [],
    }


def replay_authorized(snapshot: dict[str, list[str]], identity: IntegrationIdentity) -> bool:
    current = authorization_snapshot(identity)
    return all(set(snapshot.get(key, [])).issubset(values) for key, values in current.items())


async def reserve(
    identity: IntegrationIdentity,
    key: str,
    fingerprint: str,
    method: str,
    path: str,
) -> Reservation:
    if not KEY_PATTERN.fullmatch(key):
        raise APIError(
            "IDEMPOTENCY_KEY_REQUIRED", "Informe Idempotency-Key (8 a 128 caracteres).", 400
        )
    key_hash = sha256(key.encode()).hexdigest()
    async with integration_session(identity.context) as session:
        # A short transaction lock serializes quota and reservation for this actor,
        # not the business operation itself. Distinct actors stay independent.
        await session.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:actor,13))"),
            {"actor": identity.actor_key},
        )
        row = (
            (
                await session.execute(
                    text(
                        "select * from service_api_requests where actor_key=:actor and key_hash=:key"
                    ),
                    {"actor": identity.actor_key, "key": key_hash},
                )
            )
            .mappings()
            .first()
        )
        if row:
            if row["fingerprint"] != fingerprint:
                raise APIError(
                    "IDEMPOTENCY_CONFLICT", "Chave já utilizada com outra requisição.", 409
                )
            if not replay_authorized(row["authorization_snapshot"], identity):
                raise APIError(
                    "IDEMPOTENCY_REPLAY_FORBIDDEN",
                    "As permissões foram reduzidas "
                    "desde a operação original. Replay não autorizado.",
                    403,
                )
            if row["state"] == "completed" and row["response_sealed"]:
                age = (datetime.now(UTC) - row["created_at"]).total_seconds()
                if age <= config.replay_hours * 3600:
                    return Reservation(
                        str(row["id"]), json.loads(secret_resolver.resolve(row["response_sealed"]))
                    )
            if row["state"] in {"processing", "unknown"}:
                code = (
                    "IDEMPOTENCY_IN_PROGRESS"
                    if row["state"] == "processing"
                    and (datetime.now(UTC) - row["created_at"]).total_seconds() < 120
                    else "IDEMPOTENCY_OUTCOME_UNKNOWN"
                )
                raise APIError(
                    code,
                    "Operação já recebida. Consulte seu resultado antes de repetir.",
                    409,
                    {"request_id": str(row["id"]), "retry_after": 5},
                )
            raise APIError(
                "IDEMPOTENCY_REPLAY_EXPIRED",
                "Resultado não disponível para replay. "
                "A operação não será executada novamente com esta chave.",
                409,
                {"request_id": str(row["id"])},
            )
        count = (
            await session.execute(
                text(
                    "select count(*) from service_api_requests where actor_key=:actor "
                    "and state in ('processing','unknown')"
                ),
                {"actor": identity.actor_key},
            )
        ).scalar_one()
        if count >= config.max_pending_requests and not (
            identity.token_id is None and path.endswith("/resolve-outcome")
        ):
            raise APIError("IDEMPOTENCY_CAPACITY", "Há operações pendentes de conferência.", 429)
        request_id = str(uuid4())
        await session.execute(
            text(
                "insert into service_api_requests(id,actor_key,key_hash,fingerprint,method,path,authorization_snapshot) "
                "values(cast(:id as uuid),:actor,:key,:fingerprint,:method,:path,cast(:grants as jsonb))"
            ),
            {
                "id": request_id,
                "actor": identity.actor_key,
                "key": key_hash,
                "fingerprint": fingerprint,
                "method": method,
                "path": path[:512],
                "grants": json.dumps(authorization_snapshot(identity)),
            },
        )
        await session.commit()
        return Reservation(request_id)


async def complete(
    identity: IntegrationIdentity,
    request_id: str,
    status: int,
    headers: list[tuple[bytes, bytes]],
    body: bytes | None,
) -> None:
    saved = None
    if body is not None:
        allowed = {
            b"content-type",
            b"content-disposition",
            b"location",
            b"retry-after",
            b"content-encoding",
        }
        saved = seal_secret(
            json.dumps(
                {
                    "status": status,
                    "headers": [
                        [k.decode("latin1"), v.decode("latin1")] for k, v in headers if k in allowed
                    ],
                    "body": base64.b64encode(body).decode("ascii"),
                }
            )
        )
    async with integration_session(identity.context) as session:
        await session.execute(
            text(
                "update service_api_requests set state=:state,response_status=:status,"
                "response_sealed=:saved,completed_at=now() "
                "where id=cast(:id as uuid) and actor_key=:actor and state='processing'"
            ),
            {
                "id": request_id,
                "actor": identity.actor_key,
                "status": status,
                "saved": saved,
                "state": "completed" if saved else "response_expired",
            },
        )
        await session.commit()


async def mark_unknown(identity: IntegrationIdentity, request_id: str) -> None:
    async with integration_session(identity.context) as session:
        await session.execute(
            text(
                "update service_api_requests set state='unknown' "
                "where id=cast(:id as uuid) and actor_key=:actor and state='processing'"
            ),
            {"id": request_id, "actor": identity.actor_key},
        )
        await session.commit()
