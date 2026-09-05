import asyncio
import base64
import logging

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import APIError, error_payload
from app.core.transient_errors import is_transient_database_error
from app.integration_services.auth import (
    authenticate_management,
    authenticate_token,
    resolve_scope,
)
from app.integration_services.catalog import SAFE_METHODS, match_operation
from app.integration_services.config import integration_settings as config
from app.integration_services.ledger import complete, mark_unknown, request_fingerprint, reserve

logger = logging.getLogger("scheduler.integration-services")
MANAGEMENT_PATHS = ("/api/v1/integrations/services", "/api/v1/platform/integrations/services")


def management_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in MANAGEMENT_PATHS)


class ServiceAPIMiddleware:
    def __init__(self, app: ASGIApp, application: FastAPI) -> None:
        self.app = app
        self.application = application
        self.inflight = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        header = request.headers.get("authorization", "")
        scheme, _, raw = header.partition(" ")
        machine = raw.startswith(("sp_t_", "sp_p_"))
        managed = management_path(scope["path"])
        if not machine and not managed:
            await self.app(scope, receive, send)
            return
        if self.inflight >= config.max_inflight_requests:
            await self._error(
                APIError("API_SERVICES_BUSY", "Integrações temporariamente ocupadas.", 503),
                scope,
                receive,
                send,
            )
            return
        self.inflight += 1
        try:
            await self.dispatch(scope, receive, send, request, scheme, raw, machine)
        finally:
            self.inflight -= 1

    async def dispatch(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        request: Request,
        scheme: str,
        raw: str,
        machine: bool,
    ) -> None:
        try:
            if scheme.lower() != "bearer" or not raw:
                raise APIError("AUTH_REQUIRED", "Autenticação Bearer obrigatória.", 401)
            platform = scope["path"].startswith("/api/v1/platform/")
            context = await resolve_scope(request, platform)
            if machine:
                permission = match_operation(self.application, scope, platform)
                if permission is None:
                    raise APIError(
                        "API_RESOURCE_NOT_DELEGATED",
                        "Operação não disponível para tokens "
                        "de serviço. Consulte o catálogo ou utilize a sessão interativa.",
                        403,
                    )
                identity = await authenticate_token(raw, context, permission)
            else:
                identity = await authenticate_management(request, context, raw)
            scope.setdefault("state", {})["integration_identity"] = identity
            scope["state"]["integration_principal"] = identity.principal
        except APIError as exc:
            await self._error(exc, scope, receive, send)
            return
        except Exception as exc:
            logger.error("integration_request_rejected", extra={"error_type": type(exc).__name__})
            await self._error(
                APIError(
                    "API_DEPENDENCY_UNAVAILABLE",
                    "Serviço de integração temporariamente indisponível.",
                    503,
                ),
                scope,
                receive,
                send,
            )
            return

        if scope["method"] in SAFE_METHODS:

            async def private_send(message: Message) -> None:
                if message["type"] == "http.response.start":
                    message = dict(message)
                    message["headers"] = [
                        (k, v)
                        for k, v in message.get("headers", [])
                        if k.lower() != b"cache-control"
                    ] + [(b"cache-control", b"no-store")]
                await send(message)

            await self.app(scope, receive, private_send)
            return
        try:
            body = bytearray()
            async with asyncio.timeout(config.body_timeout_seconds):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > config.max_request_bytes:
                        raise APIError(
                            "API_REQUEST_TOO_LARGE", "Corpo acima do limite da API Services.", 413
                        )
                    if not message.get("more_body", False):
                        break
            fingerprint = request_fingerprint(
                scope["method"],
                scope["path"],
                scope.get("query_string", b"").decode("latin1"),
                request.headers.get("content-type", ""),
                bytes(body),
            )
            reservation = await reserve(
                identity,
                request.headers.get("idempotency-key", ""),
                fingerprint,
                scope["method"],
                scope["path"],
            )
            if reservation.replay is not None:
                stored = reservation.replay
                headers = [
                    (str(k).encode("latin1"), str(v).encode("latin1")) for k, v in stored["headers"]
                ]
                headers += [
                    (b"cache-control", b"no-store"),
                    (b"idempotency-replayed", b"true"),
                    (b"x-idempotency-request-id", reservation.id.encode()),
                ]
                payload = base64.b64decode(stored["body"])
                headers.append((b"content-length", str(len(payload)).encode()))
                await send(
                    {"type": "http.response.start", "status": stored["status"], "headers": headers}
                )
                await send({"type": "http.response.body", "body": payload})
                return
        except APIError as exc:
            await self._error(exc, scope, receive, send)
            return
        except Exception as exc:
            logger.error("integration_request_rejected", extra={"error_type": type(exc).__name__})
            await self._error(
                APIError(
                    "API_DEPENDENCY_UNAVAILABLE",
                    "Serviço de integração temporariamente indisponível.",
                    503,
                ),
                scope,
                receive,
                send,
            )
            return

        consumed = False
        started: Message | None = None
        buffered = bytearray()
        streaming = False
        finished = False

        async def body_receive() -> Message:
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        async def capture(message: Message) -> None:
            nonlocal started, streaming, finished
            if message["type"] == "http.response.start":
                started = dict(message)
                started["headers"] = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"cache-control"
                ] + [
                    (b"cache-control", b"no-store"),
                    (b"x-idempotency-request-id", reservation.id.encode()),
                ]
                return
            if message["type"] != "http.response.body" or started is None:
                await send(message)
                return
            chunk = message.get("body", b"")
            if not streaming and len(buffered) + len(chunk) <= config.max_response_bytes:
                buffered.extend(chunk)
            else:
                if not streaming:
                    streaming = True
                    await send(started)
                    if buffered:
                        await send(
                            {
                                "type": "http.response.body",
                                "body": bytes(buffered),
                                "more_body": True,
                            }
                        )
                    buffered.clear()
                await send(message)
            if not message.get("more_body", False):
                try:
                    await complete(
                        identity,
                        reservation.id,
                        started["status"],
                        started["headers"],
                        None if streaming else bytes(buffered),
                    )
                except Exception as exc:
                    # Never run the business handler again after an uncertain commit.
                    logger.error(
                        "integration_response_persistence_failed",
                        extra={"request_id": reservation.id, "error_type": type(exc).__name__},
                    )
                finished = True
                if not streaming:
                    await send(started)
                    await send({"type": "http.response.body", "body": bytes(buffered)})

        try:
            await self.app(scope, body_receive, capture)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not finished and not streaming:
                status = 503 if is_transient_database_error(exc) else 500
                await self._error(
                    APIError(
                        "IDEMPOTENCY_OUTCOME_UNKNOWN",
                        "Não foi possível confirmar o resultado. Consulte a operação antes de repetir.",
                        status,
                        {"request_id": reservation.id},
                    ),
                    scope,
                    receive,
                    send,
                )
        finally:
            if not finished:
                try:
                    await asyncio.wait_for(mark_unknown(identity, reservation.id), timeout=3)
                except (Exception, asyncio.CancelledError):
                    # The original processing reservation itself remains a durable tombstone.
                    logger.warning(
                        "integration_outcome_unknown", extra={"request_id": reservation.id}
                    )

    @staticmethod
    async def _error(exc: APIError, scope: Scope, receive: Receive, send: Send) -> None:
        headers = {"Cache-Control": "no-store"}
        if exc.status_code in {429, 503} or exc.details.get("retry_after"):
            headers["Retry-After"] = str(exc.details.get("retry_after", 5))
        response = JSONResponse(
            error_payload(exc.code, exc.message, exc.details),
            status_code=exc.status_code,
            headers=headers,
        )
        await response(scope, receive, send)
