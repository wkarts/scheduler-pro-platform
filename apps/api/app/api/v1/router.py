from fastapi import APIRouter, Depends

from app.api.deps import require_permission, require_super_admin
from app.api.v1.routes import (
    appointments,
    auth,
    availability,
    branding,
    builds,
    customers,
    files,
    health,
    landing_pages,
    platform,
    professionals,
    services,
    settings,
    whatsapp,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(
    services.router,
    prefix="/services",
    tags=["Services"],
    dependencies=[Depends(require_permission("services.manage"))],
)
api_router.include_router(
    professionals.router,
    prefix="/professionals",
    tags=["Professionals"],
    dependencies=[Depends(require_permission("professionals.manage"))],
)
api_router.include_router(
    availability.router,
    prefix="/availability",
    tags=["Availability"],
    dependencies=[Depends(require_permission("appointments.read"))],
)
api_router.include_router(
    appointments.router,
    prefix="/appointments",
    tags=["Appointments"],
    dependencies=[Depends(require_permission("appointments.create"))],
)
api_router.include_router(
    landing_pages.router,
    prefix="/landing-pages",
    tags=["Landing Pages"],
    dependencies=[Depends(require_permission("landing_pages.manage"))],
)
api_router.include_router(
    files.router,
    prefix="/files",
    tags=["Files"],
    dependencies=[Depends(require_permission("tenant.manage"))],
)
api_router.include_router(
    whatsapp.router,
    prefix="/integrations/whatsapp",
    tags=["WhatsApp"],
    dependencies=[Depends(require_permission("whatsapp.manage"))],
)
api_router.include_router(
    settings.router,
    prefix="/settings",
    tags=["Settings"],
    dependencies=[Depends(require_permission("tenant.manage"))],
)
# Manifest is public. Mutations enforce branding.manage inside branding.py.
api_router.include_router(branding.router, prefix="/branding", tags=["Branding"])
api_router.include_router(
    platform.router,
    prefix="/platform",
    tags=["Platform"],
    dependencies=[Depends(require_super_admin)],
)
api_router.include_router(
    builds.router,
    prefix="/platform/builds",
    tags=["Build Manager"],
    dependencies=[Depends(require_super_admin)],
)
