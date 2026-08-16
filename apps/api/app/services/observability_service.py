import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ObservabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_platform_schema(self) -> None:
        statements = [
            """
            create table if not exists platform_log_entries (
              id uuid primary key default uuid_generate_v4(),
              tenant_id uuid references tenants(id) on delete set null,
              source varchar(80) not null,
              service varchar(120) not null,
              level varchar(20) not null default 'INFO',
              event varchar(160) not null,
              message text not null,
              correlation_id varchar(120),
              request_id varchar(120),
              actor varchar(180),
              hostname varchar(255),
              container_name varchar(180),
              integration varchar(80),
              error_code varchar(120),
              details jsonb not null default '{}'::jsonb,
              created_at timestamptz not null default now()
            )
            """,
            "create index if not exists ix_platform_log_entries_created on platform_log_entries(created_at desc)",
            "create index if not exists ix_platform_log_entries_tenant on platform_log_entries(tenant_id, created_at desc)",
            "create index if not exists ix_platform_log_entries_source_level on platform_log_entries(source, level, created_at desc)",
            "create index if not exists ix_platform_log_entries_integration on platform_log_entries(integration, created_at desc)",
            "create index if not exists ix_platform_log_entries_service on platform_log_entries(service, created_at desc)",
            "create index if not exists ix_platform_log_entries_container on platform_log_entries(container_name, created_at desc)",
            """
            create table if not exists tenant_resource_boundaries (
              tenant_id uuid primary key references tenants(id) on delete cascade,
              database_name varchar(128) not null,
              database_user varchar(128) not null,
              storage_bucket varchar(160) not null,
              storage_prefix text not null,
              artifact_prefix text not null,
              log_retention_days integer not null default 90,
              isolation_status varchar(32) not null default 'ACTIVE',
              details jsonb not null default '{}'::jsonb,
              created_at timestamptz not null default now(),
              updated_at timestamptz not null default now()
            )
            """,
        ]
        for statement in statements:
            await self.session.execute(text(statement))
        await self.session.execute(
            text(
                """
                insert into tenant_resource_boundaries(
                  tenant_id, database_name, database_user, storage_bucket,
                  storage_prefix, artifact_prefix, details
                )
                select t.id,
                       coalesce(td.database_name, 'tenant_' || replace(t.id::text, '-', '')),
                       coalesce(td.database_user, 'tenant_' || replace(t.id::text, '-', '')),
                       coalesce(ts.bucket, 'scheduler-tenant-' || t.slug),
                       'tenants/' || t.id::text || '/',
                       'tenants/' || t.id::text || '/artifacts/',
                       jsonb_build_object('slug', t.slug, 'created_from_runtime_repair', true)
                from tenants t
                left join tenant_databases td on td.tenant_id=t.id
                left join tenant_storage ts on ts.tenant_id=t.id
                on conflict (tenant_id) do nothing
                """
            )
        )
        await self.session.commit()

    async def ensure_tenant_schema(self) -> None:
        statements = [
            """
            create table if not exists tenant_log_entries (
              id uuid primary key default uuid_generate_v4(),
              source varchar(80) not null,
              service varchar(120) not null,
              level varchar(20) not null default 'INFO',
              event varchar(160) not null,
              message text not null,
              correlation_id varchar(120),
              request_id varchar(120),
              actor varchar(180),
              integration varchar(80),
              error_code varchar(120),
              details jsonb not null default '{}'::jsonb,
              created_at timestamptz not null default now()
            )
            """,
            "create index if not exists ix_tenant_log_entries_created on tenant_log_entries(created_at desc)",
            "create index if not exists ix_tenant_log_entries_source_level on tenant_log_entries(source, level, created_at desc)",
            "create index if not exists ix_tenant_log_entries_integration on tenant_log_entries(integration, created_at desc)",
            "create index if not exists ix_tenant_log_entries_service on tenant_log_entries(service, created_at desc)",
        ]
        for statement in statements:
            await self.session.execute(text(statement))
        await self.session.commit()

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
        await self.ensure_platform_schema()
        await self.session.execute(
            text(
                """
                insert into platform_log_entries(
                  tenant_id, source, service, level, event, message,
                  correlation_id, request_id, actor, hostname, container_name,
                  integration, error_code, details
                ) values(
                  cast(:tenant_id as uuid), :source, :service, :level, :event,
                  :message, :correlation_id, :request_id, :actor, :hostname,
                  :container_name, :integration, :error_code, cast(:details as jsonb)
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

    @staticmethod
    def _add_filter(
        where: list[str],
        params: dict[str, Any],
        column: str,
        parameter: str,
        value: str | None,
        *,
        upper: bool = False,
    ) -> None:
        if not value:
            return
        where.append(f"{column} = :{parameter}")
        params[parameter] = value.upper() if upper else value

    async def list_platform_logs(
        self,
        *,
        tenant_filter: str | None = None,
        source: str | None = None,
        service: str | None = None,
        level: str | None = None,
        integration: str | None = None,
        container_name: str | None = None,
        actor: str | None = None,
        correlation_id: str | None = None,
        request_id: str | None = None,
        search: str | None = None,
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        await self.ensure_platform_schema()
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if tenant_filter:
            where.append("l.tenant_id = cast(:tenant_filter as uuid)")
            params["tenant_filter"] = tenant_filter
        self._add_filter(where, params, "l.source", "source", source)
        self._add_filter(where, params, "l.service", "service", service)
        self._add_filter(where, params, "l.level", "level", level, upper=True)
        self._add_filter(where, params, "l.integration", "integration", integration)
        self._add_filter(where, params, "l.container_name", "container_name", container_name)
        self._add_filter(where, params, "l.actor", "actor", actor)
        self._add_filter(where, params, "l.correlation_id", "correlation_id", correlation_id)
        self._add_filter(where, params, "l.request_id", "request_id", request_id)
        if search:
            where.append(
                "(" 
                "l.message ilike :search or l.event ilike :search or "
                "l.service ilike :search or coalesce(l.error_code, '') ilike :search or "
                "coalesce(l.actor, '') ilike :search or "
                "coalesce(l.container_name, '') ilike :search or "
                "cast(l.details as text) ilike :search"
                ")"
            )
            params["search"] = f"%{search}%"
        clause = "where " + " and ".join(where) if where else ""
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select l.id::text, l.tenant_id::text,
                           t.name as tenant_name, t.slug as tenant_slug,
                           l.source, l.service, l.level, l.event, l.message,
                           l.correlation_id, l.request_id, l.actor, l.hostname,
                           l.container_name, l.integration, l.error_code,
                           l.details, l.created_at
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
        await self.ensure_platform_schema()
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
        by_service = (
            await self.session.execute(
                text(
                    """
                    select service, count(*) as total,
                           count(*) filter(where level in ('ERROR','CRITICAL')) as errors
                    from platform_log_entries
                    where created_at >= now() - interval '24 hours'
                    group by service
                    order by total desc, service
                    limit 30
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
                           rb.storage_prefix, rb.artifact_prefix,
                           rb.isolation_status, rb.log_retention_days
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
            "by_service": [dict(row) for row in by_service],
            "tenant_boundaries": [dict(row) for row in boundaries],
        }

    async def list_tenant_logs(
        self,
        *,
        source: str | None = None,
        service: str | None = None,
        level: str | None = None,
        integration: str | None = None,
        actor: str | None = None,
        correlation_id: str | None = None,
        request_id: str | None = None,
        search: str | None = None,
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        await self.ensure_tenant_schema()
        where: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        self._add_filter(where, params, "source", "source", source)
        self._add_filter(where, params, "service", "service", service)
        self._add_filter(where, params, "level", "level", level, upper=True)
        self._add_filter(where, params, "integration", "integration", integration)
        self._add_filter(where, params, "actor", "actor", actor)
        self._add_filter(where, params, "correlation_id", "correlation_id", correlation_id)
        self._add_filter(where, params, "request_id", "request_id", request_id)
        if search:
            where.append(
                "(message ilike :search or event ilike :search or "
                "service ilike :search or coalesce(error_code, '') ilike :search or "
                "coalesce(actor, '') ilike :search or cast(details as text) ilike :search)"
            )
            params["search"] = f"%{search}%"
        clause = "where " + " and ".join(where) if where else ""
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select id::text, source, service, level, event, message,
                           correlation_id, request_id, actor, integration,
                           error_code, details, created_at
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
