import re
import secrets
import unicodedata

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import TenantStatus
from app.core.errors import APIError
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
from app.services.observability_service import ObservabilityService

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

BUILD_TARGETS = ["web", "pwa", "desktop", "android", "ios", "admin-desktop", "admin-android", "admin-ios"]


def _slug_fragment(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return (cleaned[:36].strip("-") or "cliente")


class ProvisioningService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.logs = ObservabilityService(session)

    async def _reserve_slug(self, name: str, requested_slug: str | None) -> str:
        prefix = _slug_fragment(requested_slug or name)
        for _ in range(40):
            candidate = f"{prefix}-{secrets.token_hex(4)}"
            exists = (
                await self.session.execute(select(Tenant.id).where(Tenant.slug == candidate))
            ).scalar_one_or_none()
            if exists is None:
                return candidate
        raise APIError("TENANT_SLUG_EXHAUSTED", "Não foi possível gerar código único do cliente.", 500)

    async def enqueue_tenant(self, name: str, slug: str | None, admin_email: str) -> dict[str, str]:
        reserved_slug = await self._reserve_slug(name, slug)
        tenant = Tenant(name=name, slug=reserved_slug, status=TenantStatus.pending.value)
        self.session.add(tenant)
        await self.session.flush()

        short_id = str(tenant.id).replace("-", "")[:8]
        database_name = f"tenant_{short_id}"
        database_user = f"{database_name}_user"
        storage_bucket = f"tenant-{short_id}"
        storage_prefix = f"tenants/{tenant.id}/"
        artifact_prefix = f"tenants/{tenant.id}/artifacts/"
        self.session.add(
            TenantDatabase(
                tenant_id=tenant.id,
                database_name=database_name,
                database_user=database_user,
                password_ref=f"secret://postgres/{database_name}",
            )
        )
        self.session.add(TenantStorage(tenant_id=tenant.id, bucket=storage_bucket))
        await self.session.execute(
            text(
                """
                insert into tenant_resource_boundaries(
                  tenant_id, database_name, database_user, storage_bucket,
                  storage_prefix, artifact_prefix, isolation_status, details
                ) values(
                  :tenant_id::uuid, :database_name, :database_user, :storage_bucket,
                  :storage_prefix, :artifact_prefix, 'PENDING', cast(:details as jsonb)
                )
                on conflict (tenant_id) do update set
                  database_name=excluded.database_name,
                  database_user=excluded.database_user,
                  storage_bucket=excluded.storage_bucket,
                  storage_prefix=excluded.storage_prefix,
                  artifact_prefix=excluded.artifact_prefix,
                  isolation_status=excluded.isolation_status,
                  details=excluded.details,
                  updated_at=now()
                """
            ),
            {
                "tenant_id": str(tenant.id),
                "database_name": database_name,
                "database_user": database_user,
                "storage_bucket": storage_bucket,
                "storage_prefix": storage_prefix,
                "artifact_prefix": artifact_prefix,
                "details": '{"database_per_tenant":true,"storage_per_tenant":true,"artifacts_per_tenant":true,"logs_per_tenant":true}',
            },
        )

        hostname = f"{reserved_slug}.{settings.tenant_domain_root}".lower()
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
            settings={"admin_email": admin_email, "tenant_slug": reserved_slug},
        )
        self.session.add(branding)
        await self.session.flush()

        api_url = f"https://{hostname}/api/v1" if hostname != "localhost" else "http://localhost:8000/api/v1"
        package_slug = reserved_slug.replace("-", "")
        for target in BUILD_TARGETS:
            self.session.add(
                BuildProfile(
                    tenant_id=tenant.id,
                    branding_profile_id=branding.id,
                    name=f"{name} {target.upper()}",
                    target=target,
                    bundle_identifier=f"br.com.argws.schedulerpro.{package_slug}.{target.replace('-', '')}",
                    package_name=f"br.com.argws.schedulerpro.{package_slug}.{target.replace('-', '')}" if target in {"android", "ios", "admin-android", "admin-ios"} else None,
                    api_url=api_url,
                    features=["appointments", "customers", "whatsapp", "landing", "branding"],
                    config={
                        "tenant_slug": reserved_slug,
                        "hostname": hostname,
                        "storage_prefix": storage_prefix,
                        "artifact_prefix": artifact_prefix,
                        "admin_target": target.startswith("admin-"),
                    },
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
        await self.logs.record_platform_log(
            tenant_id=str(tenant.id),
            source="provisioning",
            service="control-plane",
            level="INFO",
            event="tenant_enqueued",
            message="Tenant criado com recursos isolados e job de provisionamento enfileirado.",
            correlation_id=job.correlation_id,
            details={
                "database_name": database_name,
                "storage_bucket": storage_bucket,
                "storage_prefix": storage_prefix,
                "artifact_prefix": artifact_prefix,
                "build_targets": BUILD_TARGETS,
            },
        )
        await self.session.commit()
        return {
            "tenant_id": str(tenant.id),
            "tenant_code": reserved_slug,
            "job_id": str(job.id),
            "admin_email": admin_email,
            "hostname": hostname,
            "status": job.status,
        }
