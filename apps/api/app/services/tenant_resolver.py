from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.tenant_context import TenantContext
from app.db.models_platform import Domain, Tenant, TenantDatabase, TenantStorage


class TenantResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, hostname: str) -> TenantContext:
        stmt = (
            select(Tenant, TenantDatabase, TenantStorage, Domain)
            .join(Domain, Domain.tenant_id == Tenant.id)
            .join(TenantDatabase, TenantDatabase.tenant_id == Tenant.id)
            .join(TenantStorage, TenantStorage.tenant_id == Tenant.id)
            .where(Domain.hostname == hostname)
        )
        row = (await self.session.execute(stmt)).first()
        if row is None:
            if hostname in {"localhost", "127.0.0.1"}:
                return TenantContext(
                    tenant_id="dev-tenant",
                    slug="dev",
                    database="tenant_dev",
                    database_user="scheduler",
                    database_password_ref="scheduler_dev_password",
                    storage_bucket="tenant-dev",
                    hostname=hostname,
                )
            raise APIError("TENANT_NOT_FOUND", "Tenant não encontrado para o hostname informado.", 404, {"hostname": hostname})
        tenant, database, storage, domain = row
        return TenantContext(
            tenant_id=str(tenant.id),
            slug=tenant.slug,
            database=database.database_name,
            database_user=database.database_user,
            database_password_ref=database.password_ref,
            storage_bucket=storage.bucket,
            hostname=domain.hostname,
            timezone=tenant.timezone,
        )
