from typing import Any

from fastapi import Request, status
from fastapi.responses import ORJSONResponse

from app.core.transient_errors import is_transient_database_error


class APIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def error_payload(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def api_error_handler(_: Request, exc: Exception) -> ORJSONResponse:
    if not isinstance(exc, APIError):
        raise exc
    return ORJSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


async def unhandled_error_handler(
    request: Request,
    exc: Exception,
) -> ORJSONResponse:
    details: dict[str, Any] = {
        "request_id": getattr(request.state, "request_id", None)
    }
    if is_transient_database_error(exc):
        return ORJSONResponse(
            status_code=503,
            headers={"Retry-After": "5", "Cache-Control": "no-store"},
            content=error_payload(
                "DATABASE_TEMPORARILY_UNAVAILABLE",
                "Serviço temporariamente ocupado. Aguarde alguns segundos e tente novamente.",
                {**details, "retryable": True},
            ),
        )
    if getattr(request.app, "debug", False):
        details["exception"] = exc.__class__.__name__
    return ORJSONResponse(
        status_code=500,
        content=error_payload(
            "INTERNAL_SERVER_ERROR",
            "Falha interna inesperada.",
            details,
        ),
    )
