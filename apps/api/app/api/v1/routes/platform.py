import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_platform_tenant_access,
    get_platform_session,
    require_platform_permission,
)
from app.core.config import settings
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.cloudflare_service import CloudflareService
from app.services.domain_provisioning_service import DomainProvisioningService
from app.services.feature_service import FeatureService
from app.services.local_acme_service import local_acme_status
from app.services.provisioning import ProvisioningService
from app.services.tenant_lifecycle_service import TenantLifecycleService
from app.workers.celery_app import celery_app

router = APIRouter()


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=80,
        pattern=r"^[a-z0-9-]+$",
    )
    admin_email: EmailStr
    admin_password: str | None = Field(default=None, min_length=12, max_length=128)


class CustomDomainRequest(BaseModel):
    hostname: str = Field(min_length=4, max_length=255)
    make_primary: bool = False


class FeatureFlagUpdate(BaseModel):
    enabled: bool
    rules: dict[str, Any] = Field(default_factory=dict)


class TenantPurgeRequest(BaseModel):
    confirmation: str = Field(min_length=2, max_length=120)
    force: bool = False


def _scope_clause(principal: AuthPrincipal, alias: str = "t") -> tuple[str, dict[str, Any]]:
    if principal.is_super_admin:
        return "", {}
    tenant_ids = list(principal.tenant_ids)
    if not tenant_ids:
        return " and false", {}
    return f" and {alias}.id = any(cast(:tenant_ids as uuid[]))", {"tenant_ids": tenant_ids}


def _tenant_filter_clause(principal: AuthPrincipal, column: str) -> tuple[str, dict[str, Any]]:
    if principal.is_super_admin:
        return "", {}
    tenant_ids = list(principal.tenant_ids)
    if not tenant_ids:
        return " and false", {}
    return f" and {column} = any(cast(:tenant_ids as uuid[]))", {"tenant_ids": tenant_ids}


@router.post("/tenants")
async def create_tenant(
    request: Request,
    payload: TenantCreateRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.create")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    job = await ProvisioningService(session).enqueue_tenant(
        payload.name,
        payload.slug,
        str(payload.admin_email),
        payload.admin_password,
    )
    if not principal.is_super_admin:
        await session.execute(
            text(
                """
                insert into platform_user_tenants(user_id, tenant_id)
                values(cast(:user_id as uuid), cast(:tenant_id as uuid))
                on conflict do nothing
                """
            ),
            {"user_id": principal.user_id, "tenant_id": job["tenant_id"]},
        )
        await session.commit()
    integration = getattr(request.state, "integration_identity", None)
    if integration is not None and integration.token_id:
        # Do not inherit unrelated tenants granted to the owner after token issuance.
        # A tenant explicitly created by this token is part of its own operation.
        await session.execute(text(
            "update service_api_tokens set tenant_ids=tenant_ids || jsonb_build_array(cast(:tenant as text)) "
            "where id=cast(:token as uuid) and owner_id=cast(:owner as uuid) "
            "and not (tenant_ids ? :tenant)"
        ), {"token": integration.token_id, "owner": principal.user_id, "tenant": job["tenant_id"]})
        await session.commit()
    celery_app.send_task(
        "app.workers.tasks.run_provisioning",
        args=[job["job_id"], job["tenant_id"], f"provision-{job['job_id']}"],
        queue="provisioning",
    )
    return success(job)


@router.get("/tenants")
async def tenants(
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    scope, params = _scope_clause(principal)
    rows = (
        await session.execute(
            text(
                f"""
                select
                  t.id::text, t.name, t.slug, t.status, t.created_at,
                  d.hostname as primary_hostname,
                  b.public_name as branding_name,
                  coalesce((select count(*) from tenant_capabilities tc
                            where tc.tenant_id=t.id and tc.enabled=true), 0) as capabilities_enabled
                from tenants t
                left join domains d on d.tenant_id=t.id and d.is_primary=true
                left join tenant_branding_profiles b on b.tenant_id=t.id
                where true {scope}
                order by t.created_at desc
                limit 500
                """
            ),
            params,
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.get("/provisioning")
async def provisioning(
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    scope, params = _tenant_filter_clause(principal, "pj.tenant_id")
    jobs = (
        await session.execute(
            text(
                f"""
                select pj.id::text, pj.tenant_id::text, t.name as tenant_name,
                       t.slug, pj.status, pj.correlation_id, pj.created_at, pj.updated_at
                from provisioning_jobs pj
                join tenants t on t.id=pj.tenant_id
                where true {scope}
                order by pj.created_at desc
                limit 300
                """
            ),
            params,
        )
    ).mappings().all()
    result: list[dict[str, Any]] = []
    for job in jobs:
        steps = (
            await session.execute(
                text(
                    """
                    select id::text, name, status, error
                    from provisioning_steps
                    where job_id=cast(:id as uuid)
                    order by id
                    """
                ),
                {"id": job["id"]},
            )
        ).mappings().all()
        item = dict(job)
        item["steps"] = [dict(step) for step in steps]
        result.append(item)
    return success(result)


@router.post("/provisioning/{job_id}/retry")
async def retry_provisioning(
    job_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.provision")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                select id::text, tenant_id::text, correlation_id, status, updated_at,
                       (updated_at < now() - interval '10 minutes') as is_stale
                from provisioning_jobs
                where id=cast(:id as uuid)
                """
            ),
            {"id": job_id},
        )
    ).mappings().first()
    if row is None:
        raise APIError("PROVISIONING_JOB_NOT_FOUND", "Job de provisionamento não encontrado.", 404)
    assert_platform_tenant_access(principal, row["tenant_id"])
    current_status = str(row["status"]).upper()
    if current_status == "ACTIVE":
        raise APIError(
            "PROVISIONING_JOB_ACTIVE",
            "O tenant já está provisionado e ativo.",
            409,
        )
    if current_status in {"PENDING", "PROVISIONING"} and not bool(row["is_stale"]):
        raise APIError(
            "PROVISIONING_JOB_RUNNING",
            "O provisionamento ainda está em execução. Aguarde antes de reprocessar.",
            409,
        )
    await session.execute(
        text(
            "update provisioning_jobs set status='PENDING', updated_at=now() "
            "where id=cast(:id as uuid)"
        ),
        {"id": job_id},
    )
    await session.execute(
        text(
            """
            update provisioning_steps
            set status='pending', error=null
            where job_id=cast(:id as uuid) and status <> 'completed'
            """
        ),
        {"id": job_id},
    )
    await session.execute(
        text("update tenants set status='PENDING' where id=cast(:id as uuid)"),
        {"id": row["tenant_id"]},
    )
    await session.commit()
    celery_app.send_task(
        "app.workers.tasks.run_provisioning",
        args=[job_id, row["tenant_id"], row["correlation_id"]],
        queue="provisioning",
    )
    return success({"job_id": job_id, "queued": True})


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await TenantLifecycleService(session).suspend(tenant_id, principal.user_id))


@router.post("/tenants/{tenant_id}/restore")
async def restore_tenant(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.update")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await TenantLifecycleService(session).restore(tenant_id, principal.user_id))


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.delete")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await TenantLifecycleService(session).soft_delete(tenant_id, principal.user_id))


@router.post("/tenants/{tenant_id}/purge")
async def purge_tenant(
    tenant_id: str,
    payload: TenantPurgeRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("tenants.purge")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await TenantLifecycleService(session).purge(
            tenant_id,
            payload.confirmation,
            principal.user_id,
            force=payload.force,
        )
    )


@router.get("/domains")
async def domains(
    principal: AuthPrincipal = Depends(require_platform_permission("domains.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    scope, params = _tenant_filter_clause(principal, "d.tenant_id")
    rows = (
        await session.execute(
            text(
                f"""
                select d.id::text, d.tenant_id::text, t.name as tenant_name,
                       d.hostname, d.is_primary, d.is_temporary, d.status, d.validation
                from domains d
                join tenants t on t.id=d.tenant_id
                where true {scope}
                order by d.is_primary desc, d.hostname asc
                limit 1000
                """
            ),
            params,
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.post("/tenants/{tenant_id}/domains/temporary")
async def temporary_domain(
    tenant_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("domains.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(await DomainProvisioningService(session).create_temporary_domain(tenant_id))


@router.post("/tenants/{tenant_id}/domains/custom")
async def custom_domain(
    tenant_id: str,
    payload: CustomDomainRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("domains.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    return success(
        await DomainProvisioningService(session).connect_custom_domain(
            tenant_id,
            payload.hostname,
            make_primary=payload.make_primary,
        )
    )


async def _domain_tenant(session: AsyncSession, domain_id: str) -> str:
    tenant_id = (
        await session.execute(
            text("select tenant_id::text from domains where id=cast(:id as uuid)"),
            {"id": domain_id},
        )
    ).scalar_one_or_none()
    if tenant_id is None:
        raise APIError("DOMAIN_NOT_FOUND", "Domínio não encontrado.", 404)
    return str(tenant_id)


@router.post("/domains/{domain_id}/check")
async def check_domain(
    domain_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("domains.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, await _domain_tenant(session, domain_id))
    return success(await DomainProvisioningService(session).check_domain(domain_id))


@router.post("/domains/{domain_id}/purge-cache")
async def purge_domain_cache(
    domain_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("cache.purge")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, await _domain_tenant(session, domain_id))
    return success(await DomainProvisioningService(session).purge_domain_cache(domain_id))


@router.get("/integrations/status")
async def integration_status(
    _: AuthPrincipal = Depends(require_platform_permission("integrations.read")),
) -> dict[str, Any]:
    cloudflare: dict[str, Any] = {
        "configured": bool(settings.cloudflare_api_token),
        "ok": False,
        "zone_id_configured": bool(settings.cloudflare_zone_id),
        "zone_name_hint": settings.cloudflare_zone_name,
        "temporary_dns_proxied": settings.cloudflare_temporary_record_proxied,
    }
    if cloudflare["configured"]:
        service = CloudflareService(
            settings.cloudflare_api_token,
            settings.cloudflare_zone_id,
            api_base_url=settings.cloudflare_api_base_url,
            dry_run=settings.cloudflare_dry_run,
            custom_hostname_origin=settings.cloudflare_custom_hostname_origin,
            zone_name_hint=settings.cloudflare_zone_name,
            custom_hostname_ca=settings.cloudflare_custom_hostname_ca,
        )
        try:
            result = await service.verify_token()
            cloudflare.update(
                {"ok": bool(result.get("success", False)), "result": result.get("result")}
            )
        except Exception as exc:  # noqa: BLE001 - diagnostic endpoint
            cloudflare["error"] = str(exc)
    return success(
        {
            "cloudflare": cloudflare,
            "local_acme": local_acme_status(),
            "evolution": {
                "configured": bool(settings.evolution_api_url and settings.evolution_api_token),
                "instance_prefix": settings.evolution_instance_name,
            },
            "storage": {
                "configured": bool(
                    settings.s3_endpoint and settings.s3_access_key and settings.s3_secret_key
                ),
                "endpoint": settings.s3_endpoint,
            },
            "queues": {
                "rabbitmq": bool(settings.rabbitmq_url),
                "celery": bool(settings.celery_broker_url),
            },
        }
    )


@router.get("/audit")
async def audit(
    limit: int = 300,
    _: AuthPrincipal = Depends(require_platform_permission("audit.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            text(
                """
                select a.id::text, a.user_id::text, u.email, a.action, a.result,
                       a.ip_address, a.correlation_id, a.metadata, a.created_at
                from platform_audit_logs a
                left join platform_users u on u.id=a.user_id
                order by a.created_at desc
                limit :limit
                """
            ),
            {"limit": min(max(limit, 1), 5000)},
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.get("/feature-flags")
async def feature_flags(
    _: AuthPrincipal = Depends(require_platform_permission("settings.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await FeatureService(session).list_flags())


@router.put("/feature-flags/{key}")
async def update_feature_flag(
    key: str,
    payload: FeatureFlagUpdate,
    _: AuthPrincipal = Depends(require_platform_permission("settings.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    await session.execute(
        text(
            """
            insert into feature_flags(key, enabled, rules)
            values(:key, :enabled, cast(:rules as jsonb))
            on conflict(key) do update set enabled=excluded.enabled, rules=excluded.rules
            """
        ),
        {"key": key, "enabled": payload.enabled, "rules": json.dumps(payload.rules)},
    )
    await session.commit()
    return success({"key": key, **payload.model_dump()})


@router.get("/dashboard")
async def dashboard(
    principal: AuthPrincipal = Depends(require_platform_permission("platform.dashboard.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    if principal.is_super_admin:
        scope_sql = ""
        params: dict[str, Any] = {}
    else:
        tenant_ids = list(principal.tenant_ids)
        scope_sql = "where id = any(cast(:tenant_ids as uuid[]))" if tenant_ids else "where false"
        params = {"tenant_ids": tenant_ids}
    totals = (
        await session.execute(
            text(
                f"""
                with scoped_tenants as (select id from tenants {scope_sql})
                select
                  (select count(*) from scoped_tenants) as tenants,
                  (select count(*) from tenants where status='ACTIVE' and id in (select id from scoped_tenants)) as active_tenants,
                  (select count(*) from provisioning_jobs where tenant_id in (select id from scoped_tenants)) as provisioning_jobs,
                  (select count(*) from domains where status<>'ACTIVE' and tenant_id in (select id from scoped_tenants)) as domains_pending,
                  (select count(*) from build_jobs where tenant_id in (select id from scoped_tenants)) as builds,
                  (select count(*) from build_artifacts where tenant_id in (select id from scoped_tenants)) as build_artifacts,
                  (select count(*) from platform_users where is_active=true) as platform_users
                """
            ),
            params,
        )
    ).mappings().one()
    recent_tenants = (
        await session.execute(
            text(
                f"""
                select id::text, name, slug, status, created_at
                from tenants {scope_sql}
                order by created_at desc limit 8
                """
            ),
            params,
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
        }
    )
