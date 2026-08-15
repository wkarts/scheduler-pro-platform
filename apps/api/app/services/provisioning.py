from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import TenantStatus
from app.db.models_platform import (
    BuildProfile,
    Domain,
    ProvisioningJob,
    ProvisioningStep,
    Tenant,
    TenantBrandingProfile,
    TenantDatabase,
    TenantStorage,
)

PROVISIONING_STEPS = [
    "CreateTenant",
    "CreateDatabase",
    "RunMigrations",
    "CreateStorage",
    "CreateTemporaryDomain",
    "ConfigureCloudflare",
    "CreateAdmin",
    "SeedTenant",
    "CreateBranding",
    "CreateBuildProfiles",
    "ActivateTenant",
]

BUILD_TARGETS = ["web", "pwa", "desktop", "android", "ios"]


class ProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue_tenant(self, name: str, slug: str, admin_email: str) -> dict[str, str]:
        tenant = Tenant(name=name, slug=slug, status=TenantStatus.pending.value)
        self.session.add(tenant)
        await self.session.flush()

        short_id = str(tenant.id).replace("-", "")[:8]
        database_name = f"tenant_{short_id}"
        self.session.add(
            TenantDatabase(
                tenant_id=tenant.id,
                database_name=database_name,
                database_user=f"{database_name}_user",
                password_ref=f"secret://postgres/{database_name}",
            )
        )
        self.session.add(TenantStorage(tenant_id=tenant.id, bucket=f"tenant-{short_id}"))

        hostname = f"{slug}.{settings.tenant_domain_root}".lower()
        self.session.add(
            Domain(
                tenant_id=tenant.id,
                hostname=hostname,
                is_primary=True,
                is_temporary=True,
                status="PENDING",
                validation={"mode": "temporary"},
            )
        )

        branding = TenantBrandingProfile(
            tenant_id=tenant.id,
            status="DRAFT",
            app_name=name,
            public_name=name,
            slogan="Agendamento online simples, profissional e conectado.",
            settings={"admin_email": admin_email, "tenant_slug": slug},
        )
        self.session.add(branding)
        await self.session.flush()

        api_url = f"https://{hostname}/api/v1" if hostname != "localhost" else "http://localhost:8000/api/v1"
        for target in BUILD_TARGETS:
            self.session.add(
                BuildProfile(
                    tenant_id=tenant.id,
                    branding_profile_id=branding.id,
                    name=f"{name} {target.upper()}",
                    target=target,
                    bundle_identifier=f"br.com.schedulerpro.{slug}.{target}",
                    package_name=f"br.com.schedulerpro.{slug}.{target}" if target in {"android", "ios"} else None,
                    api_url=api_url,
                    features=["appointments", "customers", "whatsapp", "landing", "branding"],
                    config={"tenant_slug": slug, "hostname": hostname},
                )
            )

        job = ProvisioningJob(
            tenant_id=tenant.id,
            status="PENDING",
            correlation_id=settings.new_id("corr"),
        )
        self.session.add(job)
        await self.session.flush()
        for step in PROVISIONING_STEPS:
            self.session.add(ProvisioningStep(job_id=job.id, name=step))
        await self.session.commit()
        return {
            "tenant_id": str(tenant.id),
            "job_id": str(job.id),
            "admin_email": admin_email,
            "hostname": hostname,
            "status": job.status,
        }
