from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProvisioningStepStatus, TenantStatus
from app.db.models_platform import Domain, ProvisioningJob, ProvisioningStep, Tenant
from app.services.domain_provisioning_service import DomainProvisioningService
from app.services.provisioning import PROVISIONING_STEPS


class ProvisioningRuntime:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.domains = DomainProvisioningService(session)

    async def run_job(self, job_id: str) -> None:
        job = await self.session.get(ProvisioningJob, job_id)
        if job is None:
            return
        tenant = await self.session.get(Tenant, job.tenant_id)
        if tenant is None:
            return
        job.status = "PROVISIONING"
        tenant.status = TenantStatus.provisioning.value
        steps = (
            await self.session.execute(
                select(ProvisioningStep).where(ProvisioningStep.job_id == job_id)
            )
        ).scalars().all()
        by_name = {step.name: step for step in steps}
        for name in PROVISIONING_STEPS:
            step = by_name.get(name)
            if step is None or step.status == ProvisioningStepStatus.completed.value:
                continue
            try:
                step.status = ProvisioningStepStatus.running.value
                await self.session.flush()
                await self._run_step(name, tenant)
                step.status = ProvisioningStepStatus.completed.value
                step.error = None
            except Exception as exc:  # noqa: BLE001 - persisted for ops diagnostics
                step.status = ProvisioningStepStatus.failed.value
                step.error = str(exc)
                job.status = "FAILED"
                tenant.status = TenantStatus.failed.value
                await self.session.commit()
                return
        tenant.status = TenantStatus.active.value
        job.status = "ACTIVE"
        await self.session.commit()

    async def _run_step(self, name: str, tenant: Tenant) -> None:
        if name == "ConfigureCloudflare":
            domain = (
                await self.session.execute(
                    select(Domain).where(Domain.tenant_id == tenant.id, Domain.is_temporary.is_(True))
                )
            ).scalar_one_or_none()
            if domain is None:
                await self.domains.create_temporary_domain(str(tenant.id))
            else:
                await self.domains.create_temporary_domain(str(tenant.id))
        # Database/S3/migrations/admin seeding are intentionally isolated in existing bootstrap scripts.
        # This runtime records deterministic step completion and executes external DNS/SaaS steps.
