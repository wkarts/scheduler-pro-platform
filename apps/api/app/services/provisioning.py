from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import TenantStatus
from app.db.models_platform import Domain, ProvisioningJob, ProvisioningStep, Tenant, TenantDatabase, TenantStorage

PROVISIONING_STEPS = [
    "CreateTenant",
    "CreateDatabase",
    "RunMigrations",
    "CreateStorage",
    "CreateTemporaryDomain",
    "ConfigureCloudflare",
    "CreateAdmin",
    "SeedTenant",
    "ActivateTenant",
]


class ProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue_tenant(self, name: str, slug: str, admin_email: str) -> dict[str, str]:
        tenant = Tenant(name=name, slug=slug, status=TenantStatus.pending.value)
        self.session.add(tenant)
        await self.session.flush()

        short_id = str(tenant.id).replace("-", "")[:8]
        database_name = f"tenant_{short_id}"
        self.session.add(TenantDatabase(tenant_id=tenant.id, database_name=database_name, database_user=f"{database_name}_user", password_ref=f"secret://postgres/{database_name}"))
        self.session.add(TenantStorage(tenant_id=tenant.id, bucket=f"tenant-{short_id}"))
        self.session.add(Domain(tenant_id=tenant.id, hostname=f"{slug}.{settings.public_platform_domain}", is_primary=True, is_temporary=True))

        job = ProvisioningJob(tenant_id=tenant.id, status="PENDING", correlation_id=settings.new_id("corr"))
        self.session.add(job)
        await self.session.flush()
        for step in PROVISIONING_STEPS:
            self.session.add(ProvisioningStep(job_id=job.id, name=step))
        await self.session.commit()
        return {"tenant_id": str(tenant.id), "job_id": str(job.id), "admin_email": admin_email, "status": job.status}
