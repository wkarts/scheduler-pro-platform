from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, require_super_admin
from app.core.responses import success
from app.services.domain_provisioning_service import DomainProvisioningService
from app.services.provisioning import ProvisioningService

router = APIRouter()


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    admin_email: str


class CustomDomainRequest(BaseModel):
    hostname: str = Field(min_length=4, max_length=255)
    make_primary: bool = False


@router.post("/tenants")
async def create_tenant(
    payload: TenantCreateRequest,
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = ProvisioningService(session)
    job = await service.enqueue_tenant(payload.name, payload.slug, payload.admin_email)
    return success(job)


@router.get("/tenants")
async def tenants(
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            text(
                """
                select t.id::text, t.name, t.slug, t.status, t.created_at,
                       d.hostname as primary_hostname,
                       b.public_name as branding_name
                from tenants t
                left join domains d on d.tenant_id=t.id and d.is_primary=true
                left join tenant_branding_profiles b on b.tenant_id=t.id
                order by t.created_at desc
                limit 100
                """
            )
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.get("/domains")
async def domains(
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            text(
                """
                select d.id::text, d.tenant_id::text, t.name as tenant_name, d.hostname,
                       d.is_primary, d.is_temporary, d.status, d.validation
                from domains d
                join tenants t on t.id=d.tenant_id
                order by d.is_primary desc, d.hostname asc
                limit 200
                """
            )
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.post("/tenants/{tenant_id}/domains/temporary")
async def temporary_domain(
    tenant_id: str,
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await DomainProvisioningService(session).create_temporary_domain(tenant_id))


@router.post("/tenants/{tenant_id}/domains/custom")
async def custom_domain(
    tenant_id: str,
    payload: CustomDomainRequest,
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    data = await DomainProvisioningService(session).connect_custom_domain(
        tenant_id,
        payload.hostname,
        make_primary=payload.make_primary,
    )
    return success(data)


@router.post("/domains/{domain_id}/check")
async def check_domain(
    domain_id: str,
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await DomainProvisioningService(session).check_domain(domain_id))


@router.post("/domains/{domain_id}/purge-cache")
async def purge_domain_cache(
    domain_id: str,
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await DomainProvisioningService(session).purge_domain_cache(domain_id))


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
