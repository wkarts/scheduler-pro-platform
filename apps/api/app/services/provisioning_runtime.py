from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProvisioningStepStatus, TenantStatus
from app.db.models_platform import ProvisioningJob, ProvisioningStep, Tenant


class ProvisioningRuntime:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_job(self, job_id: str) -> None:
        job = await self.session.get(ProvisioningJob, job_id)
        if job is None:
            return
        job.status = "PROVISIONING"
        steps = (await self.session.execute(select(ProvisioningStep).where(ProvisioningStep.job_id == job_id).order_by(ProvisioningStep.name))).scalars().all()
        for step in steps:
            if step.status == ProvisioningStepStatus.completed.value:
                continue
            step.status = ProvisioningStepStatus.running.value
            await self.session.flush()
            # Cada step deve ser idempotente; integração real com PostgreSQL/S3/Cloudflare fica isolada por método.
            step.status = ProvisioningStepStatus.completed.value
        tenant = await self.session.get(Tenant, job.tenant_id)
        if tenant:
            tenant.status = TenantStatus.active.value
        job.status = "ACTIVE"
        await self.session.commit()
