"""Authenticated inbound JSON events. Receipt is not authorization to run business commands."""

import asyncio
from hashlib import sha256
from hmac import compare_digest
import json
import logging
import re
from secrets import token_urlsafe
import time
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import text

from app.core.errors import APIError, error_payload
from app.core.secrets import seal_secret, secret_resolver
from app.integration_services.auth import audit, current_owner, integration_session, resolve_scope
from app.integration_services.config import integration_settings as config
from app.integration_services.webhooks import signature

logger = logging.getLogger("scheduler.webhook-inbox")
IDENTIFIER = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$"
RECEIVER_FIELDS = "id::text,name,auth_mode,events,active,rate_limit,created_by::text,created_at,updated_at,last_received_at,revoked_at"
INBOX_FIELDS = "i.id::text,i.receiver_id::text,i.external_id,i.event_type,i.received_at,i.state,i.reviewed_at,i.reviewed_by::text,(i.payload_sealed is not null and i.payload_expires_at>now()) as payload_available"


class ReceiverEdit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    events: list[str] = Field(default_factory=lambda: ["*"], min_length=1, max_length=100)
    active: bool = True
    rate_limit: int = Field(default=120, ge=1, le=1000)

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str]) -> list[str]:
        if any(
            event != "*" and (len(event) > 100 or not re.fullmatch(IDENTIFIER, event))
            for event in value
        ):
            raise ValueError("Informe tipos de evento válidos ou *.")
        return sorted(set(value))


class ReceiverInput(ReceiverEdit):
    auth_mode: Literal["hmac", "bearer"] = "hmac"


class InboxStateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["acknowledged", "ignored"]


class IncomingEnvelope(BaseModel):
    # Extra signed metadata is retained, but is never interpreted as executable configuration.
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=128, pattern=IDENTIFIER, strict=True)
    type: str = Field(min_length=1, max_length=100, pattern=IDENTIFIER, strict=True)
    data: dict[str, Any]


def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("Duplicate JSON key")
        values[key] = value
    return values


def reject_constant(value: str) -> Any:
    raise ValueError("Non-finite JSON number")


def parse_event(body: bytes) -> tuple[IncomingEnvelope, str, str]:
    try:
        document = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=no_duplicate_keys,
            parse_constant=reject_constant,
        )
        event = IncomingEnvelope.model_validate(document)
        canonical = json.dumps(
            document, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
        return event, canonical, sha256(canonical.encode()).hexdigest()
    except (ValueError, TypeError, RecursionError, ValidationError) as exc:
        raise APIError(
            "WEBHOOK_PAYLOAD_INVALID", "Envie JSON UTF-8 com id, type e data (objeto).", 422
        ) from exc


def verify_signature(secret: str, request: Request, body: bytes) -> None:
    timestamp = request.headers.get("x-scheduler-timestamp", "")
    delivery_id = request.headers.get("x-scheduler-delivery-id", "")
    supplied = request.headers.get("x-scheduler-signature", "")
    if (
        not re.fullmatch(r"[0-9]{10,12}", timestamp)
        or abs(time.time() - int(timestamp)) > 300
        or len(delivery_id) > 128
        or not re.fullmatch(IDENTIFIER, delivery_id)
        or not re.fullmatch(r"v1=[a-f0-9]{64}", supplied)
        or not compare_digest(supplied, signature(secret, timestamp, delivery_id, body))
    ):
        raise APIError("WEBHOOK_AUTH_INVALID", "Credencial ou assinatura inválida.", 401)


def receiver_view(row: Any, platform: bool) -> dict[str, Any]:
    return {
        **dict(row),
        "receive_path": f"/api/v1/hooks/{'platform' if platform else 'tenant'}/{row['id']}",
        "expires_at": None,
    }


async def accept_event(request: Request, receiver_id: UUID, platform: bool) -> JSONResponse:
    if not config.incoming_webhooks_enabled:
        raise APIError("WEBHOOK_INBOX_DISABLED", "Recebimento de webhooks desativado.", 503)
    if request.query_params:
        raise APIError(
            "WEBHOOK_QUERY_NOT_ALLOWED",
            "Credenciais e eventos não devem ser enviados pela URL.",
            400,
        )
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise APIError("WEBHOOK_CONTENT_TYPE", "Utilize Content-Type: application/json.", 415)
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise APIError("WEBHOOK_ENCODING", "Envie o JSON sem compressão.", 415)
    bearer = request.headers.get("authorization", "")
    supplied = request.headers.get("x-scheduler-signature", "")
    if not bearer and not supplied:
        raise APIError("WEBHOOK_AUTH_INVALID", "Credencial ou assinatura obrigatória.", 401)
    # Bounded body is read before leasing a database connection.
    body = bytearray()
    try:
        async with asyncio.timeout(config.body_timeout_seconds):
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > config.inbox_max_bytes:
                    raise APIError(
                        "WEBHOOK_PAYLOAD_TOO_LARGE", "Evento acima do limite permitido.", 413
                    )
    except TimeoutError as exc:
        raise APIError("WEBHOOK_BODY_TIMEOUT", "Tempo de envio do evento esgotado.", 408) from exc
    event, canonical, fingerprint = parse_event(bytes(body))
    context = await resolve_scope(request, platform)
    async with integration_session(context) as session:
        row = (
            (
                await session.execute(
                    text(
                        "select * from service_webhook_receivers where id=cast(:id as uuid) "
                        "and active and revoked_at is null for update"
                    ),
                    {"id": str(receiver_id)},
                )
            )
            .mappings()
            .first()
        )
        if row is None or row["created_by"] is None:
            raise APIError("WEBHOOK_AUTH_INVALID", "Receptor ou credencial indisponível.", 401)
        if row["auth_mode"] == "hmac":
            verify_signature(secret_resolver.resolve(row["secret_ref"]), request, bytes(body))
        else:
            scheme, _, credential = bearer.partition(" ")
            if scheme.lower() != "bearer" or not compare_digest(
                sha256(credential.encode()).hexdigest(), row["secret_hash"]
            ):
                raise APIError("WEBHOOK_AUTH_INVALID", "Credencial ou assinatura inválida.", 401)
        try:
            owner = await current_owner(session, str(row["created_by"]), context)
        except APIError as exc:
            raise APIError(
                "WEBHOOK_AUTH_INVALID", "Titular do receptor indisponível.", 401
            ) from exc
        if (platform and not owner.is_super_admin) or (
            not platform and "tenant.manage" not in owner.permissions
        ):
            raise APIError("WEBHOOK_AUTH_INVALID", "Titular sem autorização para o receptor.", 401)
        if event.type not in row["events"] and "*" not in row["events"]:
            raise APIError(
                "WEBHOOK_EVENT_NOT_ALLOWED", "Tipo de evento não permitido neste receptor.", 422
            )
        usage = (
            await session.execute(
                text(
                    "update service_webhook_receivers set window_requests=case "
                    "when window_start=date_trunc('minute',now()) then window_requests+1 else 1 end,"
                    "window_start=date_trunc('minute',now()) where id=cast(:id as uuid) returning window_requests"
                ),
                {"id": str(receiver_id)},
            )
        ).scalar_one()
        if usage > row["rate_limit"]:
            await session.commit()
            raise APIError(
                "WEBHOOK_RATE_LIMIT",
                "Limite de recebimentos do receptor atingido.",
                429,
                {"retry_after": 60},
            )
        previous = (
            (
                await session.execute(
                    text(
                        "select id::text,fingerprint,state from service_webhook_inbox where receiver_id=cast(:receiver as uuid) and external_id=:event"
                    ),
                    {"receiver": str(receiver_id), "event": event.id},
                )
            )
            .mappings()
            .first()
        )
        if previous is not None:
            await session.commit()
            if not compare_digest(previous["fingerprint"], fingerprint):
                raise APIError(
                    "WEBHOOK_EVENT_CONFLICT", "Identificador já recebido com outro conteúdo.", 409
                )
            return JSONResponse(
                {
                    "data": {
                        "receipt_id": previous["id"],
                        "event_id": event.id,
                        "state": previous["state"],
                        "duplicate": True,
                    }
                },
                headers={"Cache-Control": "no-store"},
            )
        # A short, database-local lock protects the bounded payload storage quota.
        await session.execute(text("select pg_advisory_xact_lock(7313,4)"))
        await session.execute(
            text(
                "update service_webhook_inbox set payload_sealed=null where payload_sealed is not null and payload_expires_at<=now()"
            )
        )
        count = await session.scalar(
            text("select count(*) from service_webhook_inbox where payload_sealed is not null")
        )
        if int(count or 0) >= config.inbox_max_payloads:
            await session.commit()
            raise APIError(
                "WEBHOOK_INBOX_FULL",
                "Limite de eventos armazenados atingido; aguarde a retenção ou descarte conteúdos já conferidos.",
                503,
                {"retry_after": 60},
            )
        receipt_id = str(uuid4())
        await session.execute(
            text(
                "insert into service_webhook_inbox(id,receiver_id,external_id,event_type,fingerprint,payload_sealed,payload_expires_at) "
                "values(cast(:id as uuid),cast(:receiver as uuid),:event,:type,:fingerprint,:payload,now()+make_interval(days=>:days))"
            ),
            {
                "id": receipt_id,
                "receiver": str(receiver_id),
                "event": event.id,
                "type": event.type,
                "fingerprint": fingerprint,
                "payload": seal_secret(canonical),
                "days": config.retention_days,
            },
        )
        await session.execute(
            text(
                "update service_webhook_receivers set last_received_at=now() where id=cast(:id as uuid)"
            ),
            {"id": str(receiver_id)},
        )
        await session.commit()
    return JSONResponse(
        {
            "data": {
                "receipt_id": receipt_id,
                "event_id": event.id,
                "state": "received",
                "duplicate": False,
            }
        },
        status_code=202,
        headers={"Cache-Control": "no-store"},
    )


def build_ingress_router(platform: bool) -> APIRouter:
    router = APIRouter(tags=["Webhook Services — entrada"])
    inflight = 0

    @router.post("/{receiver_id}")
    async def receive_event(request: Request, receiver_id: UUID) -> JSONResponse:
        nonlocal inflight
        if inflight >= config.inbox_max_inflight:
            return JSONResponse(
                error_payload("WEBHOOK_INBOX_BUSY", "Recebimento temporariamente ocupado.", {}),
                status_code=503,
                headers={"Retry-After": "5", "Cache-Control": "no-store"},
            )
        inflight += 1
        try:
            return await accept_event(request, receiver_id, platform)
        except APIError as exc:
            headers = {"Cache-Control": "no-store"}
            if exc.status_code in {429, 503}:
                headers["Retry-After"] = str(exc.details.get("retry_after", 5))
            return JSONResponse(
                error_payload(exc.code, exc.message, exc.details),
                status_code=exc.status_code,
                headers=headers,
            )
        except Exception as exc:
            logger.warning("webhook_inbox_unavailable", extra={"error_type": type(exc).__name__})
            return JSONResponse(
                error_payload(
                    "WEBHOOK_INBOX_UNAVAILABLE",
                    "Não foi possível confirmar o recebimento. Reenvie o mesmo id e conteúdo.",
                    {},
                ),
                status_code=503,
                headers={"Retry-After": "5", "Cache-Control": "no-store"},
            )
        finally:
            inflight -= 1

    return router


def add_management_routes(router: APIRouter) -> None:
    # Lazy import keeps the existing authentication and management policy in one place.
    from app.integration_services.routes import ActiveInput, data, identity, webhook_identity

    @router.get("/receivers")
    async def receivers(request: Request) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            f"select {RECEIVER_FIELDS} from service_webhook_receivers order by created_at desc limit 100"
                        )
                    )
                )
                .mappings()
                .all()
            )
            return data([receiver_view(row, current.platform) for row in rows])

    @router.post("/receivers", status_code=201)
    async def create_receiver(request: Request, body: ReceiverInput) -> dict[str, Any]:
        current = webhook_identity(request)
        identity(request, interactive=True)
        identifier = str(uuid4())
        secret = "whin_" + token_urlsafe(32)
        async with integration_session(current.context) as session:
            await session.execute(text("select pg_advisory_xact_lock(7313,3)"))
            count = await session.scalar(
                text("select count(*) from service_webhook_receivers where revoked_at is null")
            )
            if int(count or 0) >= config.max_endpoints:
                raise APIError("WEBHOOK_RECEIVER_QUOTA", "Limite de receptores atingido.", 409)
            row = (
                (
                    await session.execute(
                        text(
                            "insert into service_webhook_receivers(id,name,created_by,auth_mode,secret_ref,secret_hash,events,active,rate_limit) "
                            "values(cast(:id as uuid),:name,cast(:owner as uuid),:mode,:secret,:hash,cast(:events as jsonb),:active,:rate) "
                            f"returning {RECEIVER_FIELDS}"
                        ),
                        {
                            "id": identifier,
                            "name": body.name,
                            "owner": current.principal.user_id,
                            "mode": body.auth_mode,
                            "secret": seal_secret(secret) if body.auth_mode == "hmac" else None,
                            "hash": sha256(secret.encode()).hexdigest(),
                            "events": json.dumps(body.events),
                            "active": body.active,
                            "rate": body.rate_limit,
                        },
                    )
                )
                .mappings()
                .one()
            )
            await audit(session, current.principal.user_id, "webhook_receiver.created", identifier)
            await session.commit()
            return data({**receiver_view(row, current.platform), "secret": secret})

    @router.put("/receivers/{receiver_id}")
    async def update_receiver(
        request: Request, receiver_id: UUID, body: ReceiverEdit
    ) -> dict[str, Any]:
        current = webhook_identity(request)
        identity(request, interactive=True)
        async with integration_session(current.context) as session:
            row = (
                (
                    await session.execute(
                        text(
                            "update service_webhook_receivers set name=:name,events=cast(:events as jsonb),active=:active,rate_limit=:rate,updated_at=now() "
                            "where id=cast(:id as uuid) and revoked_at is null "
                            + f"returning {RECEIVER_FIELDS}"
                        ),
                        {
                            "id": str(receiver_id),
                            "name": body.name,
                            "events": json.dumps(body.events),
                            "active": body.active,
                            "rate": body.rate_limit,
                        },
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("WEBHOOK_RECEIVER_NOT_FOUND", "Receptor ativo não encontrado.", 404)
            await audit(
                session, current.principal.user_id, "webhook_receiver.updated", str(receiver_id)
            )
            await session.commit()
            return data(receiver_view(row, current.platform))

    @router.post("/receivers/{receiver_id}/rotate-secret")
    async def rotate_receiver(request: Request, receiver_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        identity(request, interactive=True)
        secret = "whin_" + token_urlsafe(32)
        async with integration_session(current.context) as session:
            row = (
                (
                    await session.execute(
                        text(
                            "update service_webhook_receivers set secret_ref=case when auth_mode='hmac' then :secret else null end,secret_hash=:hash,updated_at=now() "
                            "where id=cast(:id as uuid) and revoked_at is null "
                            + f"returning {RECEIVER_FIELDS}"
                        ),
                        {
                            "id": str(receiver_id),
                            "secret": seal_secret(secret),
                            "hash": sha256(secret.encode()).hexdigest(),
                        },
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("WEBHOOK_RECEIVER_NOT_FOUND", "Receptor ativo não encontrado.", 404)
            await audit(
                session, current.principal.user_id, "webhook_receiver.rotated", str(receiver_id)
            )
            await session.commit()
            return data({**receiver_view(row, current.platform), "secret": secret})

    @router.patch("/receivers/{receiver_id}/status")
    async def receiver_status(
        request: Request, receiver_id: UUID, body: ActiveInput
    ) -> dict[str, Any]:
        current = webhook_identity(request)
        identity(request, interactive=True)
        async with integration_session(current.context) as session:
            found = await session.scalar(
                text(
                    "update service_webhook_receivers set active=:active,updated_at=now() where id=cast(:id as uuid) and revoked_at is null returning id::text"
                ),
                {"id": str(receiver_id), "active": body.active},
            )
            if found is None:
                raise APIError("WEBHOOK_RECEIVER_NOT_FOUND", "Receptor ativo não encontrado.", 404)
            await audit(
                session, current.principal.user_id, "webhook_receiver.status", str(receiver_id)
            )
            await session.commit()
            return data({"id": found, "active": body.active})

    @router.delete("/receivers/{receiver_id}")
    async def revoke_receiver(request: Request, receiver_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        identity(request, interactive=True)
        async with integration_session(current.context) as session:
            found = await session.scalar(
                text(
                    "update service_webhook_receivers set active=false,revoked_at=coalesce(revoked_at,now()),updated_at=now() where id=cast(:id as uuid) returning id::text"
                ),
                {"id": str(receiver_id)},
            )
            if found is None:
                raise APIError("WEBHOOK_RECEIVER_NOT_FOUND", "Receptor não encontrado.", 404)
            await audit(
                session, current.principal.user_id, "webhook_receiver.revoked", str(receiver_id)
            )
            await session.commit()
            return data({"id": found, "revoked": True})

    @router.get("/inbox")
    async def inbox(
        request: Request, offset: int = 0, receiver_id: UUID | None = None
    ) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            f"select {INBOX_FIELDS},r.name as receiver_name from service_webhook_inbox i join service_webhook_receivers r on r.id=i.receiver_id "
                            "where (cast(:receiver as uuid) is null or i.receiver_id=cast(:receiver as uuid)) order by i.received_at desc,i.id limit 50 offset :offset"
                        ),
                        {
                            "receiver": str(receiver_id) if receiver_id else None,
                            "offset": max(0, min(offset, 100000)),
                        },
                    )
                )
                .mappings()
                .all()
            )
            return data([dict(row) for row in rows])

    @router.get("/inbox/{receipt_id}")
    async def receipt(request: Request, receipt_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            row = (
                (
                    await session.execute(
                        text(
                            f"select {INBOX_FIELDS},case when i.payload_expires_at>now() then i.payload_sealed else null end as sealed from service_webhook_inbox i where i.id=cast(:id as uuid)"
                        ),
                        {"id": str(receipt_id)},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("WEBHOOK_RECEIPT_NOT_FOUND", "Recebimento não encontrado.", 404)
            result = dict(row)
            sealed = result.pop("sealed")
            result["event"] = json.loads(secret_resolver.resolve(sealed)) if sealed else None
            return data(result)

    @router.patch("/inbox/{receipt_id}/status")
    async def receipt_status(
        request: Request, receipt_id: UUID, body: InboxStateInput
    ) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            found = await session.scalar(
                text(
                    "update service_webhook_inbox set state=:state,reviewed_by=cast(:actor as uuid),reviewed_at=now() where id=cast(:id as uuid) returning id::text"
                ),
                {"id": str(receipt_id), "state": body.state, "actor": current.principal.user_id},
            )
            if found is None:
                raise APIError("WEBHOOK_RECEIPT_NOT_FOUND", "Recebimento não encontrado.", 404)
            await audit(
                session, current.principal.user_id, "webhook_inbox.reviewed", str(receipt_id)
            )
            await session.commit()
            return data({"id": found, "state": body.state})

    @router.delete("/inbox/{receipt_id}/payload")
    async def discard_payload(request: Request, receipt_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            found = await session.scalar(
                text(
                    "update service_webhook_inbox set payload_sealed=null where id=cast(:id as uuid) and state in ('acknowledged','ignored') returning id::text"
                ),
                {"id": str(receipt_id)},
            )
            if found is None:
                raise APIError(
                    "WEBHOOK_RECEIPT_NOT_REVIEWED",
                    "Confira o recebimento antes de descartar seu conteúdo.",
                    409,
                )
            await audit(
                session,
                current.principal.user_id,
                "webhook_inbox.payload_discarded",
                str(receipt_id),
            )
            await session.commit()
            return data({"id": found, "payload_discarded": True, "deduplication_preserved": True})
