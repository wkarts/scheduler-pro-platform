"""Machine integrations are additive; existing browser routes remain unchanged."""

from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def register_integration_services(app: FastAPI) -> None:
    from app.integration_services.middleware import ServiceAPIMiddleware
    from app.integration_services.routes import build_router

    app.include_router(build_router(False), prefix="/api/v1/integrations/services")
    app.include_router(build_router(True), prefix="/api/v1/platform/integrations/services")
    app.add_middleware(ServiceAPIMiddleware, application=app)
    # Apply the existing CORS policy to middleware-generated 401/409/429/503 responses too.
    cors = next((item for item in app.user_middleware if cast(Any, item.cls) is CORSMiddleware), None)
    if cors is not None:
        app.user_middleware.remove(cors)
        app.user_middleware.insert(0, cors)
