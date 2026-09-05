from contextlib import aclosing
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    assert_platform_tenant_access,
    get_platform_session,
    get_tenant_session,
    require_platform_permission,
)
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.db.session import tenant_session, database_pool_metrics
from app.db.connection_budget import CAPACITY_SQL, capacity_snapshot
from app.core.config import settings
from app.services.diagnostics_export_service import DiagnosticsExportService
from app.services.docker_console_service import DockerConsoleService
from app.services.observability_service import ObservabilityService
from app.services.tenant_resolver import TenantResolver

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


def _visible_platform_logs(
    rows: list[dict[str, Any]],
    principal: AuthPrincipal,
) -> list[dict[str, Any]]:
    if principal.is_super_admin:
        return rows
    allowed = principal.tenant_ids
    return [
        row
        for row in rows
        if row.get("tenant_id") is None or str(row.get("tenant_id")) in allowed
    ]


@router.get("/logs")
async def platform_logs(
    tenant: str | None = Query(default=None),
    source: str | None = Query(default=None),
    service: str | None = Query(default=None),
    level: str | None = Query(default=None),
    integration: str | None = Query(default=None),
    container: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=5000),
    principal: AuthPrincipal = Depends(require_platform_permission("observability.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    if tenant:
        assert_platform_tenant_access(principal, tenant)
    rows = await ObservabilityService(session).list_platform_logs(
        tenant_filter=tenant,
        source=source,
        service=service,
        level=level,
        integration=integration,
        container_name=container,
        actor=actor,
        correlation_id=correlation_id,
        request_id=request_id,
        search=search,
        limit=limit,
    )
    return success(_visible_platform_logs(rows, principal))


@router.get("/logs/summary")
async def platform_log_summary(
    principal: AuthPrincipal = Depends(require_platform_permission("observability.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    data = await ObservabilityService(session).summary()
    if not principal.is_super_admin:
        allowed = principal.tenant_ids
        data["tenant_boundaries"] = [
            row
            for row in data.get("tenant_boundaries", [])
            if str(row.get("tenant_id")) in allowed
        ]
    return success(data)


@router.get("/logs/export")
async def export_complete_diagnostics(
    tenant: str | None = Query(default=None),
    principal: AuthPrincipal = Depends(require_platform_permission("observability.export")),
    session: AsyncSession = Depends(get_platform_session),
) -> Response:
    """Download one redacted ZIP with DB, Docker and browser diagnostics."""

    if tenant:
        assert_platform_tenant_access(principal, tenant)
    if not principal.is_super_admin and "audit.read" not in principal.permissions:
        raise APIError(
            "DIAGNOSTICS_AUDIT_PERMISSION_REQUIRED",
            "O pacote completo inclui auditoria e exige a permissão audit.read.",
            403,
        )

    allowed = None if principal.is_super_admin else set(principal.tenant_ids)
    payload, filename = await DiagnosticsExportService(session).build_bundle(
        tenant_id=tenant,
        allowed_tenant_ids=allowed,
    )
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/logs/ingest")
async def ingest_platform_log(
    payload: LogIngestRequest,
    principal: AuthPrincipal = Depends(require_platform_permission("observability.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    if payload.tenant:
        assert_platform_tenant_access(principal, payload.tenant)
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


@router.get("/tenant/{tenant_id}/logs")
async def tenant_database_logs(
    tenant_id: str,
    source: str | None = Query(default=None),
    service: str | None = Query(default=None),
    level: str | None = Query(default=None),
    integration: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=5000),
    principal: AuthPrincipal = Depends(require_platform_permission("observability.read")),
    platform_db: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(platform_db).resolve_by_id(
        tenant_id,
        require_active=False,
    )
    async with aclosing(tenant_session(context)) as _session_scope_189:
        async for tenant_db in _session_scope_189:
            rows = await ObservabilityService(tenant_db).list_tenant_logs(
                source=source,
                service=service,
                level=level,
                integration=integration,
                actor=actor,
                correlation_id=correlation_id,
                request_id=request_id,
                search=search,
                limit=limit,
            )
            return success(rows)
    return success([])


@router.get("/tenant/{tenant_id}/audit")
async def tenant_database_audit(
    tenant_id: str,
    limit: int = Query(default=300, ge=1, le=5000),
    principal: AuthPrincipal = Depends(require_platform_permission("audit.read")),
    platform_db: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    assert_platform_tenant_access(principal, tenant_id)
    context = await TenantResolver(platform_db).resolve_by_id(
        tenant_id,
        require_active=False,
    )
    async with aclosing(tenant_session(context)) as _session_scope_217:
        async for tenant_db in _session_scope_217:
            rows = (
                await tenant_db.execute(
                    text(
                        """
                        select a.id::text, a.user_id::text, u.email, a.action,
                               a.result, a.ip_address, a.correlation_id,
                               a.metadata, a.created_at
                        from audit_logs a
                        left join users u on u.id=a.user_id
                        order by a.created_at desc
                        limit :limit
                        """
                    ),
                    {"limit": limit},
                )
            ).mappings().all()
            return success([dict(row) for row in rows])
    return success([])


@router.get("/docker/health")
async def docker_console_health(
    _: AuthPrincipal = Depends(require_platform_permission("observability.read")),
) -> dict[str, Any]:
    return success(await DockerConsoleService().health())


@router.get("/docker/containers")
async def docker_containers(
    _: AuthPrincipal = Depends(require_platform_permission("observability.read")),
) -> dict[str, Any]:
    return success(await DockerConsoleService().containers())


@router.get("/docker/logs")
async def docker_logs(
    container: str = Query(min_length=1, max_length=180),
    tail: int = Query(default=500, ge=1, le=5000),
    since: int | None = Query(default=None, ge=0),
    search: str | None = Query(default=None, max_length=300),
    _: AuthPrincipal = Depends(require_platform_permission("observability.read")),
) -> dict[str, Any]:
    return success(
        await DockerConsoleService().logs(
            container,
            tail=tail,
            since=since,
            search=search,
        )
    )


@tenant_router.get("/logs")
async def tenant_logs(
    source: str | None = Query(default=None),
    service: str | None = Query(default=None),
    level: str | None = Query(default=None),
    integration: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    correlation_id: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=300, ge=1, le=5000),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(
        await ObservabilityService(session).list_tenant_logs(
            source=source,
            service=service,
            level=level,
            integration=integration,
            actor=actor,
            correlation_id=correlation_id,
            request_id=request_id,
            search=search,
            limit=limit,
        )
    )


@tenant_router.get("/audit")
async def tenant_audit(
    limit: int = Query(default=300, ge=1, le=5000),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            text(
                """
                select a.id::text, a.user_id::text, u.email, a.action,
                       a.result, a.ip_address, a.correlation_id,
                       a.metadata, a.created_at
                from audit_logs a
                left join users u on u.id=a.user_id
                order by a.created_at desc
                limit :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.get("/database")
async def database_capacity(
    _: AuthPrincipal = Depends(require_platform_permission("observability.read")),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    row = (await session.execute(text(CAPACITY_SQL))).mappings().one()
    from app.main import _log_runner
    return success({
        "capacity": capacity_snapshot(
            row, warning=settings.db_capacity_warning_percent,
            critical=settings.db_capacity_critical_percent,
        ),
        "process_pools": database_pool_metrics(),
        "http_log_buffer": _log_runner.metrics(),
    })
