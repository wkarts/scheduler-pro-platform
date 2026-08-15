from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session
from app.core.responses import success
from app.services.build_manager_service import BuildManagerService, BuildRequestInput

router = APIRouter()


class BuildRequestCreate(BaseModel):
    tenant: str = Field(min_length=8)
    target: str = Field(pattern="^(web|pwa|desktop|android|ios)$")
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


@router.get("/profiles")
async def list_profiles(
    tenant: str | None = None,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    manager = BuildManagerService(session)
    return success({"profiles": await manager.list_profiles(tenant)})


@router.post("/requests")
async def create_request(
    payload: BuildRequestCreate,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    manager = BuildManagerService(session)
    job = await manager.create_build_request(
        BuildRequestInput(
            tenant=payload.tenant,
            target=payload.target,
            profile=payload.profile,
            requested_by=payload.requested_by,
            source_ref=payload.source_ref,
            source_sha=payload.source_sha,
            payload=payload.payload,
        )
    )
    return success(job)


@router.get("/jobs")
async def list_jobs(
    tenant: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    manager = BuildManagerService(session)
    return success({"jobs": await manager.list_jobs(tenant, limit)})


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    manager = BuildManagerService(session)
    return success(await manager.get_job(job_id))


@router.post("/jobs/{job_id}/artifacts")
async def register_artifact(
    job_id: str,
    payload: ArtifactRegisterRequest,
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    manager = BuildManagerService(session)
    artifact = await manager.register_artifact(
        job_id,
        payload.artifact_type,
        payload.name,
        payload.download_url,
        payload.checksum_sha256,
        payload.size_bytes,
        payload.metadata,
    )
    return success(artifact)
