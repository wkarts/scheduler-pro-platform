from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, get_tenant_context, get_tenant_session
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.branding_service import BrandingService
from app.services.landing_service import LandingPageService

router = APIRouter()


@router.get("/landing")
async def landing(
    slug: str = "home",
    context: TenantContext = Depends(get_tenant_context),
    tenant_session: AsyncSession = Depends(get_tenant_session),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    branding = await BrandingService(platform_session).manifest_for_context(context)
    page = await LandingPageService(tenant_session).get_published(slug)
    return success({"tenant": {"id": context.tenant_id, "slug": context.slug}, "branding": branding, "landing_page": page})
