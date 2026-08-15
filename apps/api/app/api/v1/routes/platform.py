from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session
from app.core.responses import success
from app.services.provisioning import ProvisioningService

router = APIRouter()


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    admin_email: str


@router.post("/tenants")
async def create_tenant(
    payload: TenantCreateRequest,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = ProvisioningService(session)
    job = await service.enqueue_tenant(payload.name, payload.slug, payload.admin_email)
    return success(job)


@router.get("/dashboard")
async def dashboard() -> dict[str, Any]:
    return success(
        {"tenants": 0, "provisioning_jobs": 0, "builds": 0, "domains_pending": 0}
    )
