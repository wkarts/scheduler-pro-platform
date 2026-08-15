from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, require_super_admin
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
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = ProvisioningService(session)
    job = await service.enqueue_tenant(payload.name, payload.slug, payload.admin_email)
    return success(job)


@router.get("/dashboard")
async def dashboard(
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    totals = (
        await session.execute(
            text(
                """
                select
                  (select count(*) from tenants) as tenants,
                  (select count(*) from tenants where status = 'ACTIVE') as active_tenants,
                  (select count(*) from provisioning_jobs) as provisioning_jobs,
                  (select count(*) from domains where status <> 'ACTIVE') as domains_pending,
                  (select count(*) from build_jobs) as builds,
                  (select count(*) from build_artifacts) as build_artifacts,
                  (select count(*) from platform_users where is_active = true) as platform_users
                """
            )
        )
    ).mappings().one()

    recent_tenants = (
        await session.execute(
            text(
                """
                select id::text, name, slug, status, created_at
                from tenants
                order by created_at desc
                limit 6
                """
            )
        )
    ).mappings().all()

    recent_builds = (
        await session.execute(
            text(
                """
                select id::text, target, status, created_at
                from build_jobs
                order by created_at desc
                limit 6
                """
            )
        )
    ).mappings().all()

    recent_provisioning = (
        await session.execute(
            text(
                """
                select id::text, status, correlation_id, created_at
                from provisioning_jobs
                order by created_at desc
                limit 6
                """
            )
        )
    ).mappings().all()

    return success(
        {
            "totals": dict(totals),
            "health": {
                "platform": "online",
                "queue": "configured",
                "storage": "configured",
                "release": "available",
            },
            "recent_tenants": [dict(row) for row in recent_tenants],
            "recent_builds": [dict(row) for row in recent_builds],
            "recent_provisioning": [dict(row) for row in recent_provisioning],
        }
    )
