from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_platform_tenant_access,
    get_platform_session,
    require_platform_permission,
)
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.build_manager_service import BuildManagerService, BuildRequestInput

router = APIRouter()


class BuildRequestCreate(BaseModel):
    tenant: str = Field(min_length=8)
    target: str = Field(
        pattern="^(web|pwa|desktop|android|ios|admin-desktop|admin-android|admin-ios)$"
    )
    profile: str | None = None
    requested_by: str | None = None
    source_ref: str = "main"
    source_sha: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ArtifactRegisterRequest(BaseModel):
    artifact_type: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=180)
    download_url: str | None = None
    checksum_sha256: str | None = None
    size_bytes: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


async def _job_tenant(session: AsyncSession, job_id: str) -> str:
    tenant_id = (
        await session.execute(
            text("select tenant_id::text from build_jobs where id=cast(:id as uuid)"),
            {"id": job_id},
        )
    ).scalar_one_or_none()
    if tenant_id is None:
        raise APIError("BUILD_JOB_NOT_FOUND", "Job de build não encontrado.", 404)
    return str(tenant_id)


@router.get("/profiles")
async def list_profiles(
    tenant: str | None = None,
    principal: AuthPrincipal = Depends(require_platform_permission("builds.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BuildManagerService(session)
    if tenant:
        assert_platform_tenant_access(principal, tenant)
        return success({"profiles": await service.list_profiles(tenant)})
    if principal.is_super_admin:
        return success({"profiles": await service.list_profiles()})
    rows: list[dict[str, object]] = []
    for tenant_id in sorted(principal.tenant_ids):
        rows.extend(await service.list_profiles(tenant_id))
    return success({"profiles": rows})


@router.post("/requests")
async def create_request(
    payload: BuildRequestCreate,
    principal: AuthPrincipal = Depends(require_platform_permission("builds.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, payload.tenant)
    job = await BuildManagerService(session).create_build_request(
        BuildRequestInput(
            tenant=payload.tenant,
            target=payload.target,
            profile=payload.profile,
            requested_by=principal.user_id,
            source_ref=payload.source_ref,
            source_sha=payload.source_sha,
            payload=payload.payload,
        )
    )
    return success(job)


@router.get("/jobs")
async def list_jobs(
    tenant: str | None = None,
    limit: int = 100,
    principal: AuthPrincipal = Depends(require_platform_permission("builds.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = BuildManagerService(session)
    if tenant:
        assert_platform_tenant_access(principal, tenant)
        return success({"jobs": await service.list_jobs(tenant, limit)})
    if principal.is_super_admin:
        return success({"jobs": await service.list_jobs(None, limit)})
    rows: list[dict[str, object]] = []
    for tenant_id in sorted(principal.tenant_ids):
        rows.extend(await service.list_jobs(tenant_id, limit))
    rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return success({"jobs": rows[: min(max(limit, 1), 200)]})


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("builds.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, await _job_tenant(session, job_id))
    return success(await BuildManagerService(session).get_job(job_id))


@router.post("/jobs/{job_id}/refresh")
async def refresh_job(
    job_id: str,
    principal: AuthPrincipal = Depends(require_platform_permission("builds.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, await _job_tenant(session, job_id))
    return success(await BuildManagerService(session).refresh_job(job_id))


@router.post("/jobs/{job_id}/artifacts")
async def register_artifact(
    job_id: str,
    payload: ArtifactRegisterRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("builds.manage")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, await _job_tenant(session, job_id))
    artifact = await BuildManagerService(session).register_artifact(
        job_id,
        payload.artifact_type,
        payload.name,
        payload.download_url,
        payload.checksum_sha256,
        payload.size_bytes,
        payload.metadata,
    )
    return success(artifact)
