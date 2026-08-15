from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import APIError, api_error_handler, unhandled_error_handler
from app.core.logging import configure_logging
from app.db.session import close_database_engines


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await close_database_engines()


def create_app() -> FastAPI:
    configure_logging()
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
        allow_origins=settings.cors_allowed_origins,
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
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        response.headers["x-correlation-id"] = request.state.correlation_id
        return response

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
