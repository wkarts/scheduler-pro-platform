from fastapi import APIRouter

from app.api.v1.routes import appointments, auth, availability, branding, builds, customers, files, health, landing_pages, platform, professionals, services, settings, whatsapp

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(customers.router, prefix="/customers", tags=["Customers"])
api_router.include_router(services.router, prefix="/services", tags=["Services"])
api_router.include_router(professionals.router, prefix="/professionals", tags=["Professionals"])
api_router.include_router(availability.router, prefix="/availability", tags=["Availability"])
api_router.include_router(appointments.router, prefix="/appointments", tags=["Appointments"])
api_router.include_router(landing_pages.router, prefix="/landing-pages", tags=["Landing Pages"])
api_router.include_router(files.router, prefix="/files", tags=["Files"])
api_router.include_router(whatsapp.router, prefix="/integrations/whatsapp", tags=["WhatsApp"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(branding.router, prefix="/branding", tags=["Branding"])
api_router.include_router(platform.router, prefix="/platform", tags=["Platform"])
api_router.include_router(builds.router, prefix="/platform/builds", tags=["Build Manager"])
