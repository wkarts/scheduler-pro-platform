from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import APIError, api_error_handler, unhandled_error_handler
from app.core.logging import configure_logging
from app.core.security import decode_access_token
from app.db.session import close_database_engines


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await close_database_engines()


def _request_principal(request: Request) -> dict[str, Any]:
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
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Correlation-ID",
        ],
    )

    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

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
        started = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            logger.exception(
                "http_request_failed",
                request_id=request.state.request_id,
                correlation_id=request.state.correlation_id,
                method=request.method,
                path=request.url.path,
                client_ip=request.client.host if request.client else None,
                duration_ms=round((perf_counter() - started) * 1000, 3),
                **_request_principal(request),
            )
            raise
        response.headers["x-request-id"] = request.state.request_id
        response.headers["x-correlation-id"] = request.state.correlation_id
        logger.info(
            "http_request",
            request_id=request.state.request_id,
            correlation_id=request.state.correlation_id,
            method=request.method,
            path=request.url.path,
            query=request.url.query or None,
            status_code=status_code,
            duration_ms=round((perf_counter() - started) * 1000, 3),
            client_ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:240] or None,
            **_request_principal(request),
        )
        return response

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
