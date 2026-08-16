import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ObservabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_platform_log(
        self,
        *,
        source: str,
        service: str,
        event: str,
        message: str,
        level: str = "INFO",
        tenant_id: str | None = None,
        integration: str | None = None,
        error_code: str | None = None,
        correlation_id: str | None = None,
        request_id: str | None = None,
        actor: str | None = None,
        hostname: str | None = None,
        container_name: str | None = None,
        details: dict[str, Any] | None = None,
        commit: bool = False,
    ) -> None:
        await self.session.execute(
            text(
                """
                insert into platform_log_entries(
                  tenant_id, source, service, level, event, message, correlation_id, request_id,
                  actor, hostname, container_name, integration, error_code, details
                ) values(
                  cast(:tenant_id as uuid), :source, :service, :level, :event, :message,
                  :correlation_id, :request_id, :actor, :hostname, :container_name,
                  :integration, :error_code, cast(:details as jsonb)
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "source": source,
                "service": service,
                "level": level.upper(),
                "event": event,
                "message": message,
                "correlation_id": correlation_id,
                "request_id": request_id,
                "actor": actor,
                "hostname": hostname,
                "container_name": container_name,
                "integration": integration,
                "error_code": error_code,
                "details": json.dumps(details or {}, ensure_ascii=False),
            },
        )
        if commit:
            await self.session.commit()

    async def list_platform_logs(
        self,
        *,
        tenant_id: str | None = None,
        source: str | None = None,
        level: str | None = None,
        integration: str | None = None,
        search: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if tenant_id:
            where.append("tenant_id = cast(:tenant_id as uuid)")
            params["tenant_id"] = tenant_id
        if source:
            where.append("source = :source")
            params["source"] = source
        if level:
            where.append("level = :level")
            params["level"] = level.upper()
        if integration:
            where.append("integration = :integration")
            params["integration"] = integration
        if search:
            where.append("(message ilike :search or event ilike :search or service ilike :search or coalesce(error_code, '') ilike :search)")
            params["search"] = f"%{search}%"
        clause = "where " + " and ".join(where) if where else ""
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select l.id::text, l.tenant_id::text, t.name as tenant_name, t.slug as tenant_slug,
                           l.source, l.service, l.level, l.event, l.message, l.correlation_id,
                           l.request_id, l.actor, l.hostname, l.container_name, l.integration,
                           l.error_code, l.details, l.created_at
                    from platform_log_entries l
                    left join tenants t on t.id = l.tenant_id
                    {clause}
                    order by l.created_at desc
                    limit :limit
                    """
                ),
                params,
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    async def summary(self) -> dict[str, Any]:
        counts = (
            await self.session.execute(
                text(
                    """
                    select
                      count(*) as total,
                      count(*) filter (where level in ('ERROR','CRITICAL')) as errors,
                      count(*) filter (where source='docker') as docker,
                      count(*) filter (where source='integration') as integrations,
                      count(*) filter (where tenant_id is not null) as tenant_scoped
                    from platform_log_entries
                    where created_at >= now() - interval '24 hours'
                    """
                )
            )
        ).mappings().one()
        by_source = (
            await self.session.execute(
                text(
                    """
                    select source, level, count(*) as total
                    from platform_log_entries
                    where created_at >= now() - interval '24 hours'
                    group by source, level
                    order by source, level
                    """
                )
            )
        ).mappings().all()
        boundaries = (
            await self.session.execute(
                text(
                    """
                    select rb.tenant_id::text, t.name as tenant_name, t.slug,
                           rb.database_name, rb.database_user, rb.storage_bucket,
                           rb.storage_prefix, rb.artifact_prefix, rb.isolation_status,
                           rb.log_retention_days
                    from tenant_resource_boundaries rb
                    join tenants t on t.id=rb.tenant_id
                    order by t.created_at desc
                    limit 100
                    """
                )
            )
        ).mappings().all()
        return {
            "last_24h": dict(counts),
            "by_source": [dict(row) for row in by_source],
            "tenant_boundaries": [dict(row) for row in boundaries],
        }

    async def list_tenant_logs(
        self,
        *,
        source: str | None = None,
        level: str | None = None,
        integration: str | None = None,
        search: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if source:
            where.append("source = :source")
            params["source"] = source
        if level:
            where.append("level = :level")
            params["level"] = level.upper()
        if integration:
            where.append("integration = :integration")
            params["integration"] = integration
        if search:
            where.append("(message ilike :search or event ilike :search or service ilike :search or coalesce(error_code, '') ilike :search)")
            params["search"] = f"%{search}%"
        clause = "where " + " and ".join(where) if where else ""
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select id::text, source, service, level, event, message, correlation_id,
                           request_id, actor, integration, error_code, details, created_at
                    from tenant_log_entries
                    {clause}
                    order by created_at desc
                    limit :limit
                    """
                ),
                params,
            )
        ).mappings().all()
        return [dict(row) for row in rows]
