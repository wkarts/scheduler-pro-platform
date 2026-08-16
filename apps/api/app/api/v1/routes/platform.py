from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, require_super_admin
from app.core.config import settings
from app.core.responses import success
from app.services.cloudflare_service import CloudflareService
from app.services.domain_provisioning_service import DomainProvisioningService
from app.services.feature_service import FeatureService
from app.services.provisioning import ProvisioningService
from app.workers.celery_app import celery_app

router = APIRouter()


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    admin_email: EmailStr
    admin_password: str | None = Field(default=None, min_length=12, max_length=128)


class CustomDomainRequest(BaseModel):
    hostname: str = Field(min_length=4, max_length=255)
    make_primary: bool = False


class FeatureFlagUpdate(BaseModel):
    enabled: bool
    rules: dict[str, Any] = Field(default_factory=dict)


@router.post("/tenants")
async def create_tenant(payload: TenantCreateRequest, _: Any = Depends(require_super_admin), session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]:
    job = await ProvisioningService(session).enqueue_tenant(payload.name,payload.slug,str(payload.admin_email),payload.admin_password)
    celery_app.send_task("app.workers.tasks.run_provisioning",args=[job["job_id"],job["tenant_id"],f"provision-{job['job_id']}"],queue="provisioning")
    return success(job)


@router.get("/tenants")
async def tenants(_: Any = Depends(require_super_admin), session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]:
    rows=(await session.execute(text("""
        select t.id::text,t.name,t.slug,t.status,t.created_at,d.hostname as primary_hostname,b.public_name as branding_name
        from tenants t left join domains d on d.tenant_id=t.id and d.is_primary=true left join tenant_branding_profiles b on b.tenant_id=t.id
        order by t.created_at desc limit 200
    """))).mappings().all();return success([dict(row) for row in rows])


@router.get("/provisioning")
async def provisioning(_: Any = Depends(require_super_admin), session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]:
    jobs=(await session.execute(text("""
      select pj.id::text,pj.tenant_id::text,t.name as tenant_name,t.slug,pj.status,pj.correlation_id,pj.created_at
      from provisioning_jobs pj join tenants t on t.id=pj.tenant_id order by pj.created_at desc limit 100
    """))).mappings().all()
    result=[]
    for job in jobs:
        steps=(await session.execute(text("select id::text,name,status,error from provisioning_steps where job_id=:id::uuid order by id"),{"id":job["id"]})).mappings().all()
        item=dict(job);item["steps"]=[dict(step) for step in steps];result.append(item)
    return success(result)


@router.post("/provisioning/{job_id}/retry")
async def retry_provisioning(job_id: str, _: Any = Depends(require_super_admin), session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]:
    row=(await session.execute(text("select id::text,tenant_id::text,correlation_id from provisioning_jobs where id=:id::uuid"),{"id":job_id})).mappings().first()
    if row is None:
        from app.core.errors import APIError
        raise APIError("PROVISIONING_JOB_NOT_FOUND","Job de provisionamento não encontrado.",404)
    await session.execute(text("update provisioning_jobs set status='PENDING' where id=:id::uuid"),{"id":job_id})
    await session.execute(text("update provisioning_steps set status='pending',error=null where job_id=:id::uuid and status='failed'"),{"id":job_id})
    await session.execute(text("update tenants set status='PENDING' where id=:tenant_id::uuid"),{"tenant_id":row["tenant_id"]});await session.commit()
    celery_app.send_task("app.workers.tasks.run_provisioning",args=[job_id,row["tenant_id"],row["correlation_id"]],queue="provisioning")
    return success({"job_id":job_id,"queued":True})


@router.get("/domains")
async def domains(_: Any = Depends(require_super_admin), session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]:
    rows=(await session.execute(text("select d.id::text,d.tenant_id::text,t.name as tenant_name,d.hostname,d.is_primary,d.is_temporary,d.status,d.validation from domains d join tenants t on t.id=d.tenant_id order by d.is_primary desc,d.hostname asc limit 500"))).mappings().all();return success([dict(row) for row in rows])


@router.post("/tenants/{tenant_id}/domains/temporary")
async def temporary_domain(tenant_id: str, _: Any = Depends(require_super_admin), session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]: return success(await DomainProvisioningService(session).create_temporary_domain(tenant_id))
@router.post("/tenants/{tenant_id}/domains/custom")
async def custom_domain(tenant_id: str,payload: CustomDomainRequest,_: Any = Depends(require_super_admin),session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]: return success(await DomainProvisioningService(session).connect_custom_domain(tenant_id,payload.hostname,make_primary=payload.make_primary))
@router.post("/domains/{domain_id}/check")
async def check_domain(domain_id: str,_: Any = Depends(require_super_admin),session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]: return success(await DomainProvisioningService(session).check_domain(domain_id))
@router.post("/domains/{domain_id}/purge-cache")
async def purge_domain_cache(domain_id: str,_: Any = Depends(require_super_admin),session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]: return success(await DomainProvisioningService(session).purge_domain_cache(domain_id))


@router.get("/integrations/status")
async def integration_status(_: Any = Depends(require_super_admin)) -> dict[str, Any]:
    cloudflare:dict[str,Any]={"configured":bool(settings.cloudflare_api_token and settings.cloudflare_zone_id),"ok":False}
    if cloudflare["configured"]:
        try:
            result=await CloudflareService(settings.cloudflare_api_token,settings.cloudflare_zone_id,api_base_url=settings.cloudflare_api_base_url,dry_run=settings.cloudflare_dry_run,custom_hostname_origin=settings.cloudflare_custom_hostname_origin).verify_token();cloudflare.update({"ok":bool(result.get("success",False)),"result":result.get("result")})
        except Exception as exc: cloudflare["error"]=str(exc)
    return success({"cloudflare":cloudflare,"evolution":{"configured":bool(settings.evolution_api_url and settings.evolution_api_token),"instance_prefix":settings.evolution_instance_name},"storage":{"configured":bool(settings.s3_endpoint and settings.s3_access_key and settings.s3_secret_key),"endpoint":settings.s3_endpoint},"queues":{"rabbitmq":bool(settings.rabbitmq_url),"celery":bool(settings.celery_broker_url)}})


@router.get("/audit")
async def audit(limit: int = 200, _: Any = Depends(require_super_admin), session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]:
    rows=(await session.execute(text("""
      select a.id::text,a.user_id::text,u.email,a.action,a.result,a.ip_address,a.correlation_id,a.metadata,a.created_at
      from platform_audit_logs a left join platform_users u on u.id=a.user_id order by a.created_at desc limit :limit
    """),{"limit":min(max(limit,1),500)})).mappings().all();return success([dict(row) for row in rows])


@router.get("/feature-flags")
async def feature_flags(_: Any = Depends(require_super_admin),session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]: return success(await FeatureService(session).list_flags())
@router.put("/feature-flags/{key}")
async def update_feature_flag(key: str,payload: FeatureFlagUpdate,_: Any = Depends(require_super_admin),session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]:
    await session.execute(text("insert into feature_flags(key,enabled,rules) values(:key,:enabled,cast(:rules as jsonb)) on conflict(key) do update set enabled=excluded.enabled,rules=excluded.rules"),{"key":key,"enabled":payload.enabled,"rules":__import__('json').dumps(payload.rules)});await session.commit();return success({"key":key,**payload.model_dump()})


@router.get("/dashboard")
async def dashboard(_: Any = Depends(require_super_admin), session: AsyncSession = Depends(get_platform_session)) -> dict[str, Any]:
    totals=(await session.execute(text("""select (select count(*) from tenants) tenants,(select count(*) from tenants where status='ACTIVE') active_tenants,(select count(*) from provisioning_jobs) provisioning_jobs,(select count(*) from domains where status<>'ACTIVE') domains_pending,(select count(*) from build_jobs) builds,(select count(*) from build_artifacts) build_artifacts,(select count(*) from platform_users where is_active=true) platform_users"""))).mappings().one()
    recent_tenants=(await session.execute(text("select id::text,name,slug,status,created_at from tenants order by created_at desc limit 6"))).mappings().all();recent_builds=(await session.execute(text("select id::text,target,status,created_at from build_jobs order by created_at desc limit 6"))).mappings().all();recent_provisioning=(await session.execute(text("select id::text,status,correlation_id,created_at from provisioning_jobs order by created_at desc limit 6"))).mappings().all()
    return success({"totals":dict(totals),"health":{"platform":"online","queue":"configured","storage":"configured","release":"available"},"recent_tenants":[dict(r) for r in recent_tenants],"recent_builds":[dict(r) for r in recent_builds],"recent_provisioning":[dict(r) for r in recent_provisioning]})
