from fastapi import APIRouter, Depends

from app.api.deps import require_permission, require_tenant_capability
from app.api.v1.routes import (
    agenda,
    appointment_confirmations,
    appointment_edit,
    appointment_operations,
    appointments,
    auth,
    auth_two_factor,
    availability,
    branding,
    builds,
    customers,
    downloads,
    files,
    health,
    landing_pages,
    notifications,
    observability,
    password_reset_pages,
    platform,
    platform_access,
    platform_html_templates,
    platform_templates,
    platform_visual_builder,
    professionals,
    public,
    realtime,
    schedule,
    services,
    settings,
    tenant_management,
    tenant_support,
    tenant_telemetry,
    whatsapp,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(public.router, prefix="/public", tags=["Public"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(auth_two_factor.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(password_reset_pages.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(
    customers.router,
    prefix="/customers",
    tags=["Customers"],
    dependencies=[Depends(require_tenant_capability("customers"))],
)
api_router.include_router(
    services.router,
    prefix="/services",
    tags=["Services"],
    dependencies=[
        Depends(require_tenant_capability("services")),
        Depends(require_permission("services.manage")),
    ],
)
api_router.include_router(
    professionals.router,
    prefix="/professionals",
    tags=["Professionals"],
    dependencies=[
        Depends(require_tenant_capability("professionals")),
        Depends(require_permission("professionals.manage")),
    ],
)
api_router.include_router(
    schedule.router,
    prefix="/schedule",
    tags=["Schedule Configuration"],
    dependencies=[
        Depends(require_tenant_capability("appointments")),
        Depends(require_permission("professionals.manage")),
    ],
)
api_router.include_router(
    availability.router,
    prefix="/availability",
    tags=["Availability"],
    dependencies=[
        Depends(require_tenant_capability("appointments")),
        Depends(require_permission("appointments.read")),
    ],
)
api_router.include_router(
    appointments.router,
    prefix="/appointments",
    tags=["Appointments"],
    dependencies=[
        Depends(require_tenant_capability("appointments")),
        Depends(require_permission("appointments.create")),
    ],
)
api_router.include_router(
    agenda.router,
    prefix="/agenda",
    tags=["Agenda"],
    dependencies=[
        Depends(require_tenant_capability("appointments")),
        Depends(require_permission("appointments.create")),
    ],
)
api_router.include_router(
    appointment_operations.router,
    prefix="/appointments",
    tags=["Appointment Operations"],
    dependencies=[
        Depends(require_tenant_capability("appointments")),
        Depends(require_permission("appointments.create")),
    ],
)
api_router.include_router(
    appointment_edit.router,
    prefix="/appointments",
    tags=["Appointment Smart Edit"],
    dependencies=[
        Depends(require_tenant_capability("appointments")),
        Depends(require_permission("appointments.create")),
    ],
)
api_router.include_router(
    appointment_confirmations.router,
    prefix="/appointment-confirmations",
    tags=["Appointment Confirmations"],
    dependencies=[
        Depends(require_tenant_capability("appointments")),
        Depends(require_permission("appointments.create")),
    ],
)
api_router.include_router(realtime.router, prefix="/realtime", tags=["Realtime / Push"])
api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
    dependencies=[
        Depends(require_tenant_capability("notifications")),
        Depends(require_permission("notifications.manage")),
    ],
)
api_router.include_router(
    landing_pages.router,
    prefix="/landing-pages",
    tags=["Landing Pages"],
    dependencies=[
        Depends(require_tenant_capability("landing_pages")),
        Depends(require_permission("landing_pages.manage")),
    ],
)
api_router.include_router(
    files.router,
    prefix="/files",
    tags=["Files"],
    dependencies=[
        Depends(require_tenant_capability("storage")),
        Depends(require_permission("tenant.manage")),
    ],
)
api_router.include_router(
    whatsapp.router,
    prefix="/integrations/whatsapp",
    tags=["ARGWS WhatsApp API"],
    dependencies=[
        Depends(require_tenant_capability("whatsapp")),
        Depends(require_permission("whatsapp.manage")),
    ],
)
api_router.include_router(
    settings.router,
    prefix="/settings",
    tags=["Settings"],
    dependencies=[Depends(require_permission("tenant.manage"))],
)
api_router.include_router(
    observability.tenant_router,
    prefix="/observability",
    tags=["Tenant Observability"],
    dependencies=[
        Depends(require_tenant_capability("observability")),
        Depends(require_permission("tenant.manage")),
    ],
)
api_router.include_router(
    tenant_telemetry.router,
    prefix="/telemetry",
    tags=["Tenant Telemetry"],
)
api_router.include_router(
    downloads.router,
    prefix="/downloads",
    tags=["Universal App Downloads"],
)
api_router.include_router(branding.router, prefix="/branding", tags=["Branding"])
api_router.include_router(platform.router, prefix="/platform", tags=["Platform"])
api_router.include_router(
    tenant_management.router,
    prefix="/platform/tenant-management",
    tags=["Tenant Management"],
)
api_router.include_router(
    tenant_support.router,
    prefix="/platform/tenant-support",
    tags=["Tenant Support"],
)
api_router.include_router(
    platform_templates.router,
    prefix="/platform/templates",
    tags=["Global Templates"],
)
api_router.include_router(
    platform_html_templates.router,
    prefix="/platform/html-templates",
    tags=["HTML Templates"],
)
api_router.include_router(
    platform_visual_builder.router,
    prefix="/platform/visual-builder",
    tags=["ARGWS Visual Builder"],
)
api_router.include_router(
    platform_access.router,
    prefix="/platform/access",
    tags=["Platform IAM"],
)
api_router.include_router(
    observability.router,
    prefix="/platform/observability",
    tags=["Platform Observability"],
)
api_router.include_router(
    builds.router,
    prefix="/platform/builds",
    tags=["Build Manager"],
)
