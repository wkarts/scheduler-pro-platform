from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_platform_session, get_tenant_session, require_super_admin
from app.core.responses import success
from app.services.observability_service import ObservabilityService

router = APIRouter()
tenant_router = APIRouter()


class LogIngestRequest(BaseModel):
    tenant: str | None = None
    source: str = Field(min_length=2, max_length=80)
    service: str = Field(min_length=2, max_length=120)
    level: str = Field(default="INFO", max_length=20)
    event: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=1)
    correlation_id: str | None = None
    request_id: str | None = None
    actor: str | None = None
    hostname: str | None = None
    container_name: str | None = None
    integration: str | None = None
    error_code: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


@router.get("/logs")
async def platform_logs(
    tenant: str | None = Query(default=None),
    source: str | None = Query(default=None),
    level: str | None = Query(default=None),
    integration: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = ObservabilityService(session)
    return success(
        await service.list_platform_logs(
            tenant_id=tenant,
            source=source,
            level=level,
            integration=integration,
            search=search,
            limit=limit,
        )
    )


@router.get("/logs/summary")
async def platform_log_summary(
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    return success(await ObservabilityService(session).summary())


@router.post("/logs/ingest")
async def ingest_platform_log(
    payload: LogIngestRequest,
    _: Any = Depends(require_super_admin),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    await ObservabilityService(session).record_platform_log(
        tenant_id=payload.tenant,
        source=payload.source,
        service=payload.service,
        level=payload.level,
        event=payload.event,
        message=payload.message,
        correlation_id=payload.correlation_id,
        request_id=payload.request_id,
        actor=payload.actor,
        hostname=payload.hostname,
        container_name=payload.container_name,
        integration=payload.integration,
        error_code=payload.error_code,
        details=payload.details,
        commit=True,
    )
    return success({"accepted": True})


@tenant_router.get("/logs")
async def tenant_logs(
    source: str | None = Query(default=None),
    level: str | None = Query(default=None),
    integration: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(
        await ObservabilityService(session).list_tenant_logs(
            source=source,
            level=level,
            integration=integration,
            search=search,
            limit=limit,
        )
    )
