import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.public_appointment_actions import router as appointment_action_router
from app.api.v1.router import api_router
from app.core.background_tasks import BoundedTaskRunner
from app.core.config import settings
from app.core.errors import APIError, api_error_handler, unhandled_error_handler
from app.core.logging import configure_logging
from app.core.security import decode_access_token
from app.core.transient_errors import is_transient_database_error
from app.db.engine_registry import DatabaseCapacityError
from app.db.session import PlatformSession, close_database_engines, reap_idle_tenant_engines
from app.distribution_sync import run as run_distribution_sync
from app.services.http_log_persistence import persist_http_operation, should_persist_http_operation
from app.services.observability_service import ObservabilityService

_log_runner = BoundedTaskRunner(
    maximum=settings.http_log_max_pending,
    concurrency=settings.http_log_concurrency,
    timeout=settings.http_log_timeout_seconds,
)
_reaper_task: asyncio.Task[None] | None = None
_distribution_task: asyncio.Task[None] | None = None


def _distribution_sync_enabled() -> bool:
    raw = os.getenv("DISTRIBUTION_SYNC_ENABLED")
    if raw is None:
        return settings.app_env != "development"
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _distribution_task, _reaper_task, _log_runner
    _log_runner = BoundedTaskRunner(
        maximum=settings.http_log_max_pending,
        concurrency=settings.http_log_concurrency,
        timeout=settings.http_log_timeout_seconds,
    )
    _reaper_task = asyncio.create_task(reap_idle_tenant_engines(), name="tenant-pool-reaper")
    try:
        async with PlatformSession() as session:
            await ObservabilityService(session).ensure_platform_schema()
    except Exception:
        # Observability must not prevent the API from starting; readiness still
        # reports the actual dependency state and later log writes are fail-open.
        pass

    if _distribution_sync_enabled():
        _distribution_task = asyncio.create_task(
            run_distribution_sync(),
            name="scheduler-pro-distribution-sync",
        )

    try:
        yield
    finally:
        await _shutdown_runtime()


async def _shutdown_runtime() -> None:
    global _distribution_task, _reaper_task
    if _distribution_task is not None:
        _distribution_task.cancel()
        await asyncio.gather(_distribution_task, return_exceptions=True)
        _distribution_task = None
    if _reaper_task is not None:
        _reaper_task.cancel()
        await asyncio.gather(_reaper_task, return_exceptions=True)
        _reaper_task = None
    from app.api.v1.routes.health import close_readiness_tasks
    await close_readiness_tasks()
    await _log_runner.close(grace=5)
    await close_database_engines()


def _request_principal(request: Request) -> dict[str, Any]:
    service = getattr(request.state, "integration_identity", None)
    if service is not None and service.token_id:
        principal = service.principal
        return {"user_id": principal.user_id, "tenant_id": principal.tenant_id,
                "user_type": principal.user_type, "session_id": principal.session_id,
                "api_token_id": service.token_id}
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return {}
    try:
        payload = decode_access_token(authorization.split(" ", 1)[1].strip())
    except APIError:
        return {}
    return {
        "user_id": payload.get("sub"),
        "tenant_id": payload.get("tenant_id"),
        "user_type": payload.get("user_type"),
        "session_id": payload.get("sid"),
    }


def _queue_http_log(
    request: Request,
    *,
    status_code: int,
    duration_ms: float,
    principal: dict[str, Any],
    error_type: str | None = None,
) -> None:
    if not should_persist_http_operation(request.url.path, status_code):
        return
    _log_runner.submit(
        lambda: persist_http_operation(
            method=request.method,
            path=request.url.path,
            query=None if request.url.path.startswith("/api/v1/hooks/") else request.url.query or None,
            status_code=status_code,
            duration_ms=duration_ms,
            request_id=request.state.request_id,
            correlation_id=request.state.correlation_id,
            host=request.headers.get("host", ""),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            principal=principal,
            error_type=error_type,
        )
    )


def create_app() -> FastAPI:
    configure_logging()
    logger = structlog.get_logger("scheduler.api")
    app = FastAPI(
        title="Scheduler Pro API",
        version="0.1.0-alpha.1",
        default_response_class=ORJSONResponse,
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.effective_cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        expose_headers=["X-Request-ID", "X-Correlation-ID", "X-Idempotency-Request-ID",
                        "Idempotency-Replayed", "Retry-After"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Correlation-ID",
            "Idempotency-Key",
            "Idempotency-Key",
        ],
    )

    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(DatabaseCapacityError, unhandled_error_handler)
    app.add_exception_handler(SQLAlchemyError, unhandled_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.state.inflight_requests = 0

    @app.middleware("http")
    async def correlation_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.request_id = (
            request.headers.get("x-request-id") or settings.new_id("req")
        )
        request.state.correlation_id = (
            request.headers.get("x-correlation-id") or settings.new_id("corr")
        )
        principal = _request_principal(request)
        started = perf_counter()
        status_code = 500
        response: Response
        try:
            exempt = request.url.path in {
                "/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready", "/api/v1/version",
            } or request.method == "OPTIONS"
            if not exempt and app.state.inflight_requests >= settings.api_max_inflight_requests:
                response = ORJSONResponse(
                    status_code=503,
                    headers={"Retry-After": "5", "Cache-Control": "no-store"},
                    content={"error": {
                        "code": "SERVICE_BUSY",
                        "message": "Serviço temporariamente ocupado. Tente novamente em instantes.",
                        "details": {"request_id": request.state.request_id, "retryable": True},
                    }},
                )
            else:
                if not exempt:
                    app.state.inflight_requests += 1
                try:
                    response = await call_next(request)
                finally:
                    if not exempt:
                        app.state.inflight_requests -= 1
            status_code = response.status_code
        except Exception as exc:
            duration_ms = round((perf_counter() - started) * 1000, 3)
            logger.exception(
                "http_request_failed",
                request_id=request.state.request_id,
                correlation_id=request.state.correlation_id,
                method=request.method,
                path=request.url.path,
                client_ip=request.client.host if request.client else None,
                duration_ms=duration_ms,
                **principal,
            )
            _queue_http_log(
                request,
                status_code=503 if is_transient_database_error(exc) else 500,
                duration_ms=duration_ms,
                principal=principal,
                error_type=type(exc).__name__,
            )
            raise

        duration_ms = round((perf_counter() - started) * 1000, 3)
        response.headers["x-request-id"] = request.state.request_id
        response.headers["x-correlation-id"] = request.state.correlation_id
        logger.info(
            "http_request",
            request_id=request.state.request_id,
            correlation_id=request.state.correlation_id,
            method=request.method,
            path=request.url.path,
            query=None if request.url.path.startswith("/api/v1/hooks/") else request.url.query or None,
            status_code=status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:240] or None,
            **principal,
        )
        _queue_http_log(
            request,
            status_code=status_code,
            duration_ms=duration_ms,
            principal=principal,
        )
        return response

    # URL curta pública usada nas mensagens de confirmação/cancelamento.
    # É resolvida pelo hostname do tenant e não exige autenticação.
    app.include_router(appointment_action_router)
    app.include_router(api_router, prefix="/api/v1")
    from app.integration_services import register_integration_services
    register_integration_services(app)
    return app


app = create_app()
