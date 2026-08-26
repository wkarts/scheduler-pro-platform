from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.tenant_context import DEFAULT_TENANT_STORAGE_QUOTA_BYTES, TenantContext


class TenantResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _validate_status(row: Any) -> None:
        domain_status = str(row["domain_status"]).upper()
        if domain_status != "ACTIVE":
            raise APIError(
                "DOMAIN_NOT_ACTIVE",
                "Domínio do tenant ainda não está ativo.",
                503,
                {"status": domain_status},
            )
        status = str(row["tenant_status"]).upper()
        if status == "SUSPENDED":
            raise APIError("TENANT_SUSPENDED", "Tenant suspenso.", 403)
        if status != "ACTIVE":
            raise APIError(
                "TENANT_NOT_ACTIVE",
                "Tenant ainda não está ativo.",
                503,
                {"status": status},
            )

    @staticmethod
    def _storage_quota(row: Any) -> int:
        tenant_settings = row.get("tenant_settings") if hasattr(row, "get") else None
        if not isinstance(tenant_settings, dict):
            return DEFAULT_TENANT_STORAGE_QUOTA_BYTES
        raw = tenant_settings.get("storage_quota_bytes")
        try:
            quota = int(raw or DEFAULT_TENANT_STORAGE_QUOTA_BYTES)
        except (TypeError, ValueError):
            return DEFAULT_TENANT_STORAGE_QUOTA_BYTES
        return min(max(quota, 128 * 1024 * 1024), 1024 * 1024 * 1024 * 1024)

    @staticmethod
    def _context(row: Any) -> TenantContext:
        return TenantContext(
            tenant_id=row["tenant_id"],
            slug=row["slug"],
            database=row["database_name"],
            database_user=row["database_user"],
            database_password_ref=row["password_ref"],
            storage_bucket=row["bucket"],
            hostname=row["hostname"],
            timezone=row["timezone"],
            database_credential_version=int(row["credential_version"] or 1),
            storage_quota_bytes=TenantResolver._storage_quota(row),
        )

    async def resolve(self, hostname: str) -> TenantContext:
        stmt = text(
            """
            select
                t.id::text as tenant_id, t.slug, t.status as tenant_status, t.timezone,
                t.settings as tenant_settings,
                td.database_name, td.database_user, td.password_ref, td.credential_version,
                ts.bucket, d.hostname, d.status as domain_status
            from tenants t
            join domains d on d.tenant_id = t.id
            join tenant_databases td on td.tenant_id = t.id
            join tenant_storage ts on ts.tenant_id = t.id
            where lower(d.hostname) = :hostname
            limit 1
            """
        )
        row = (await self.session.execute(stmt, {"hostname": hostname.lower()})).mappings().first()
        if row is None:
            if settings.app_env == "development" and hostname in {"localhost", "127.0.0.1"}:
                return TenantContext(
                    tenant_id="dev-tenant",
                    slug=settings.dev_tenant_slug,
                    database=settings.dev_tenant_database,
                    database_user=settings.dev_tenant_database_user,
                    database_password_ref=settings.dev_tenant_database_password_ref,
                    storage_bucket=settings.dev_tenant_bucket,
                    hostname=hostname,
                    database_credential_version=1,
                    storage_quota_bytes=DEFAULT_TENANT_STORAGE_QUOTA_BYTES,
                )
            raise APIError(
                "TENANT_NOT_FOUND",
                "Tenant não encontrado para o hostname informado.",
                404,
                {"hostname": hostname},
            )
        self._validate_status(row)
        return self._context(row)

    async def resolve_by_id(self, tenant_id: str, *, require_active: bool = True) -> TenantContext:
        stmt = text(
            """
            select
                t.id::text as tenant_id, t.slug, t.status as tenant_status, t.timezone,
                t.settings as tenant_settings,
                td.database_name, td.database_user, td.password_ref, td.credential_version,
                ts.bucket,
                coalesce(dp.hostname, da.hostname) as hostname,
                coalesce(dp.status, da.status, 'PENDING') as domain_status
            from tenants t
            join tenant_databases td on td.tenant_id=t.id
            join tenant_storage ts on ts.tenant_id=t.id
            left join lateral (
              select hostname, status
              from domains
              where tenant_id=t.id and is_primary=true
              order by is_temporary desc
              limit 1
            ) dp on true
            left join lateral (
              select hostname, status
              from domains
              where tenant_id=t.id
              order by is_temporary desc
              limit 1
            ) da on true
            where t.id=cast(:tenant_id as uuid)
            limit 1
            """
        )
        row = (await self.session.execute(stmt, {"tenant_id": tenant_id})).mappings().first()
        if row is None:
            raise APIError(
                "TENANT_NOT_FOUND",
                "Tenant não encontrado.",
                404,
                {"tenant_id": tenant_id},
            )
        if require_active:
            self._validate_status(row)
        hostname = row["hostname"] or f"{row['slug']}.{settings.tenant_domain_root}"
        mutable = dict(row)
        mutable["hostname"] = hostname
        return self._context(mutable)
