import asyncio
import os
import re
import sys

import asyncpg
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ProvisioningStepStatus, TenantStatus
from app.core.security import hash_password
from app.core.secrets import secret_resolver
from app.db.postgres_admin import connect_postgres_admin
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
from app.services.domain_provisioning_service import DomainProvisioningService
from app.services.mail_service import mail_delivery
from app.services.observability_service import ObservabilityService
from app.services.provisioning import BUILD_TARGETS, PROVISIONING_STEPS
from app.services.s3_bucket_admin import ensure_bucket

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TENANT_ADMIN_PERMISSIONS = [
    "appointments.read",
    "appointments.create",
    "appointments.update",
    "appointments.cancel",
    "customers.read",
    "customers.manage",
    "services.manage",
    "professionals.manage",
    "notifications.manage",
    "whatsapp.manage",
    "landing_pages.manage",
    "branding.manage",
    "reports.read",
    "tenant.manage",
    "users.read",
    "users.manage",
    "groups.manage",
    "audit.read",
]


def _identifier(value: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError("Unsafe PostgreSQL identifier.")
    return f'"{value}"'


class ProvisioningRuntime:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.domains = DomainProvisioningService(session)
        self.logs = ObservabilityService(session)

    async def run_job(self, job_id: str) -> None:
        claimed = (
            await self.session.execute(
                text(
                    """
                    update provisioning_jobs
                    set status='PROVISIONING', updated_at=now()
                    where id=cast(:id as uuid) and status='PENDING'
                    returning tenant_id::text, correlation_id
                    """
                ),
                {"id": job_id},
            )
        ).mappings().first()
        if claimed is None:
            # A entrega duplicada da tarefa ou um job já encerrado não pode executar novamente.
            await self.session.rollback()
            return

        tenant = await self.session.get(Tenant, claimed["tenant_id"])
        if tenant is None:
            await self.session.execute(
                text(
                    """
                    update provisioning_jobs
                    set status='FAILED', updated_at=now()
                    where id=cast(:id as uuid)
                    """
                ),
                {"id": job_id},
            )
            await self.session.commit()
            return

        tenant.status = TenantStatus.provisioning.value
        await self.session.commit()
        job = await self.session.get(ProvisioningJob, job_id)
        if job is None:
            return

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
            step.status = ProvisioningStepStatus.running.value
            step.error = None
            await self.session.execute(
                text("update provisioning_jobs set updated_at=now() where id=cast(:id as uuid)"),
                {"id": job_id},
            )
            await self.session.commit()
            tenant_id = str(tenant.id)
            step_id = str(step.id)
            correlation_id = job.correlation_id
            try:
                await self._run_step(name, tenant)
            except Exception as exc:  # noqa: BLE001 - persisted for ops diagnostics
                error_message = str(exc)[:4000]
                # Qualquer erro PostgreSQL pode deixar a transação SQLAlchemy abortada.
                # O rollback precisa ocorrer antes de persistir FAILED; sem isso o job
                # permanece eternamente RUNNING/PROVISIONING.
                await self.session.rollback()
                failed_step = await self.session.get(ProvisioningStep, step_id)
                failed_job = await self.session.get(ProvisioningJob, job_id)
                failed_tenant = await self.session.get(Tenant, tenant_id)
                if failed_step is not None:
                    failed_step.status = ProvisioningStepStatus.failed.value
                    failed_step.error = error_message
                if failed_job is not None:
                    failed_job.status = "FAILED"
                if failed_tenant is not None:
                    failed_tenant.status = TenantStatus.failed.value
                await self.session.execute(
                    text("update provisioning_jobs set updated_at=now() where id=cast(:id as uuid)"),
                    {"id": job_id},
                )
                await self.logs.record_platform_log(
                    tenant_id=tenant_id,
                    source="provisioning",
                    service="provisioning-runtime",
                    level="ERROR",
                    event="provisioning_step_failed",
                    message=f"Falha no passo {name}.",
                    correlation_id=correlation_id,
                    error_code="PROVISIONING_STEP_FAILED",
                    details={"step": name, "error": error_message},
                )
                await self.session.commit()
                return
            step.status = ProvisioningStepStatus.completed.value
            step.error = None
            await self.session.execute(
                text("update provisioning_jobs set updated_at=now() where id=cast(:id as uuid)"),
                {"id": job_id},
            )
            await self.session.commit()

        tenant.status = TenantStatus.active.value
        job.status = "ACTIVE"
        await self.session.execute(
            text(
                """
                update tenant_resource_boundaries
                set isolation_status='ACTIVE', updated_at=now()
                where tenant_id=cast(:tenant_id as uuid)
                """
            ),
            {"tenant_id": str(tenant.id)},
        )
        await self.session.execute(
            text("update provisioning_jobs set updated_at=now() where id=cast(:id as uuid)"),
            {"id": job_id},
        )
        await self.logs.record_platform_log(
            tenant_id=str(tenant.id),
            source="provisioning",
            service="provisioning-runtime",
            event="tenant_activated",
            message="Cliente provisionado e ativado com banco, storage, administrador, domínio e perfis isolados.",
            correlation_id=job.correlation_id,
        )
        await self.session.commit()

    async def _resources(self, tenant: Tenant) -> tuple[TenantDatabase, TenantStorage, str]:
        database = (
            await self.session.execute(select(TenantDatabase).where(TenantDatabase.tenant_id == tenant.id))
        ).scalar_one()
        storage = (
            await self.session.execute(select(TenantStorage).where(TenantStorage.tenant_id == tenant.id))
        ).scalar_one()
        password = secret_resolver.resolve(database.password_ref)
        return database, storage, password

    async def _run_step(self, name: str, tenant: Tenant) -> None:
        if name == "CreateTenant":
            return
        if name == "CreateDatabase":
            await self._create_database(tenant)
            return
        if name == "RunMigrations":
            await self._run_migrations(tenant)
            return
        if name == "CreateStorage":
            await self._create_storage(tenant)
            return
        if name == "CreateTemporaryDomain":
            domain_result = await self.domains.create_temporary_domain(str(tenant.id))
            if domain_result.get("status") != "ACTIVE":
                raise RuntimeError(
                    "Domínio temporário não convergiu para DNS proxied/ACTIVE. "
                    f"Estado: {domain_result.get('status')}"
                )
            return
        if name == "ConfigureCloudflare":
            domain_record = (
                await self.session.execute(
                    select(Domain).where(Domain.tenant_id == tenant.id, Domain.is_temporary.is_(True))
                )
            ).scalar_one_or_none()
            if domain_record is None:
                checked = await self.domains.create_temporary_domain(str(tenant.id))
            else:
                checked = await self.domains.check_domain(str(domain_record.id))
            if checked.get("status") != "ACTIVE":
                raise RuntimeError(
                    "Cloudflare não confirmou o domínio temporário como proxied/ACTIVE. "
                    f"Estado: {checked.get('status')}"
                )
            return
        if name == "CreateAdmin":
            await self._create_admin(tenant)
            return
        if name == "SeedTenant":
            await self._seed_tenant(tenant)
            return
        if name == "CreateBranding":
            profile = (
                await self.session.execute(select(TenantBrandingProfile).where(TenantBrandingProfile.tenant_id == tenant.id))
            ).scalar_one_or_none()
            if profile is None:
                raise RuntimeError("Branding profile ausente para o tenant.")
            return
        if name == "CreateBuildProfiles":
            targets = set(
                (
                    await self.session.execute(
                        select(BuildProfile.target).where(BuildProfile.tenant_id == tenant.id)
                    )
                ).scalars().all()
            )
            missing = [target for target in BUILD_TARGETS if target not in targets]
            if missing:
                raise RuntimeError(
                    "Build profiles incompletos para o tenant. "
                    f"Targets ausentes: {', '.join(missing)}"
                )
            return
        if name == "SendWelcomeEmail":
            await self._send_welcome_email(tenant)
            return
        if name == "ActivateTenant":
            return
        raise RuntimeError(f"Passo de provisionamento desconhecido: {name}")

    async def _create_database(self, tenant: Tenant) -> None:
        database, _, password = await self._resources(tenant)
        conn = await connect_postgres_admin()
        try:
            password_literal = await conn.fetchval("select quote_literal($1)", password)
            role_exists = await conn.fetchval("select exists(select 1 from pg_roles where rolname=$1)", database.database_user)
            if role_exists:
                await conn.execute(f"alter role {_identifier(database.database_user)} with login password {password_literal}")
            else:
                await conn.execute(f"create role {_identifier(database.database_user)} login password {password_literal}")
            db_exists = await conn.fetchval("select exists(select 1 from pg_database where datname=$1)", database.database_name)
            if not db_exists:
                await conn.execute(f"create database {_identifier(database.database_name)} owner {_identifier(database.database_user)}")
        finally:
            await conn.close()

    async def _run_migrations(self, tenant: Tenant) -> None:
        database, _, password = await self._resources(tenant)
        env = os.environ.copy()
        env["ALEMBIC_TENANT_DATABASE"] = database.database_name
        env["ALEMBIC_TENANT_USER"] = database.database_user
        env["ALEMBIC_TENANT_PASSWORD"] = password
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.cli",
            "migrate-tenant",
            database.database_name,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"Falha na migration tenant: {stderr.decode('utf-8', 'replace')[-3000:]}")
        if stdout:
            await self.logs.record_platform_log(
                tenant_id=str(tenant.id),
                source="provisioning",
                service="alembic",
                event="tenant_migrations_applied",
                message="Migrations do tenant aplicadas.",
                details={"output": stdout.decode("utf-8", "replace")[-1000:]},
            )

    async def _create_storage(self, tenant: Tenant) -> None:
        _, storage, _ = await self._resources(tenant)
        try:
            await asyncio.to_thread(ensure_bucket, storage.bucket)
        except (BotoCoreError, ClientError, OSError) as exc:
            raise RuntimeError(f"Falha ao criar bucket S3/MinIO {storage.bucket}: {exc}") from exc

    async def _tenant_connection(self, tenant: Tenant) -> asyncpg.Connection:
        database, _, password = await self._resources(tenant)
        return await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=database.database_user,
            password=password,
            database=database.database_name,
        )

    async def _create_admin(self, tenant: Tenant) -> None:
        tenant_settings = tenant.settings if isinstance(tenant.settings, dict) else {}
        admin_email = str(tenant_settings.get("admin_email") or "").strip().lower()
        admin_password_ref = str(tenant_settings.get("admin_password_ref") or "")
        if not admin_email or not admin_password_ref:
            raise RuntimeError("Credenciais iniciais do administrador do tenant estão ausentes.")
        admin_password = secret_resolver.resolve(admin_password_ref)
        conn = await self._tenant_connection(tenant)
        try:
            role_id = await conn.fetchval(
                """
                insert into roles(name, description)
                values('tenant-admin', 'Administrador do tenant')
                on conflict(name) do update set description=excluded.description
                returning id::text
                """
            )
            permission_ids: list[str] = []
            for permission in TENANT_ADMIN_PERMISSIONS:
                permission_id = await conn.fetchval(
                    """
                    insert into permissions(key, description) values($1, $2)
                    on conflict(key) do update set description=excluded.description
                    returning id::text
                    """,
                    permission,
                    permission,
                )
                permission_ids.append(permission_id)
            user_id = await conn.fetchval(
                """
                insert into users(email, password_hash, display_name, is_active, failed_login_attempts, locked_until, updated_at)
                values($1, $2, 'Administrador', true, 0, null, now())
                on conflict(email) do update set
                  password_hash=excluded.password_hash,
                  is_active=true,
                  failed_login_attempts=0,
                  locked_until=null,
                  updated_at=now()
                returning id::text
                """,
                admin_email,
                hash_password(admin_password),
            )
            await conn.execute(
                "insert into user_roles(user_id, role_id) values($1::uuid, $2::uuid) on conflict do nothing",
                user_id,
                role_id,
            )
            for permission_id in permission_ids:
                await conn.execute(
                    "insert into role_permissions(role_id, permission_id) values($1::uuid, $2::uuid) on conflict do nothing",
                    role_id,
                    permission_id,
                )
        finally:
            await conn.close()

    async def _seed_tenant(self, tenant: Tenant) -> None:
        conn = await self._tenant_connection(tenant)
        try:
            total_hours = await conn.fetchval("select count(*) from business_hours")
            if int(total_hours or 0) == 0:
                for day_of_week in range(1, 7):
                    await conn.execute(
                        "insert into business_hours(professional_id, day_of_week, opens_at, closes_at, is_open) values(null, $1, '08:00', '18:00', true)",
                        day_of_week,
                    )
            instance_name = f"{settings.evolution_instance_name}-{tenant.slug}"[:160]
            await conn.execute(
                """
                insert into whatsapp_integrations(name, provider, instance_name, status, settings)
                values('default', 'evolution', $1, 'DISCONNECTED', '{}'::jsonb)
                on conflict(name) do update set instance_name=excluded.instance_name, provider=excluded.provider
                """,
                instance_name,
            )
        finally:
            await conn.close()

    async def _send_welcome_email(self, tenant: Tenant) -> None:
        tenant_settings = tenant.settings if isinstance(tenant.settings, dict) else {}
        admin_email = str(tenant_settings.get("admin_email") or "").strip().lower()
        admin_password_ref = str(tenant_settings.get("admin_password_ref") or "")
        if not admin_email or not admin_password_ref:
            await self.logs.record_platform_log(
                tenant_id=str(tenant.id),
                source="provisioning",
                service="smtp",
                level="WARNING",
                event="tenant_welcome_email_skipped",
                message="E-mail de boas-vindas não enviado porque as credenciais iniciais do tenant estão ausentes.",
                error_code="TENANT_WELCOME_CREDENTIALS_MISSING",
            )
            return

        domain = (
            await self.session.execute(
                select(Domain)
                .where(Domain.tenant_id == tenant.id, Domain.status == "ACTIVE")
                .order_by(Domain.is_primary.desc(), Domain.is_temporary.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        hostname = domain.hostname if domain else f"{tenant.slug}.{settings.tenant_domain_root}"
        login_url = f"https://{hostname}"
        initial_password = secret_resolver.resolve(admin_password_ref)
        result = await asyncio.to_thread(
            mail_delivery.send_tenant_welcome,
            recipient=admin_email,
            tenant_name=tenant.name,
            tenant_code=tenant.slug,
            temporary_password=initial_password,
            login_url=login_url,
        )
        event = "tenant_welcome_email_sent" if result.delivered else "tenant_welcome_email_failed"
        await self.logs.record_platform_log(
            tenant_id=str(tenant.id),
            source="provisioning",
            service="smtp",
            level="INFO" if result.delivered else "WARNING",
            event=event,
            message=(
                "E-mail de boas-vindas e credenciais iniciais enviado ao administrador do tenant."
                if result.delivered
                else "Tenant provisionado, mas o e-mail de boas-vindas não pôde ser entregue."
            ),
            error_code=None if result.delivered else (result.error_code or "SMTP_DELIVERY_FAILED"),
            details={"recipient": admin_email, "login_url": login_url},
        )
        await self.session.execute(
            text(
                """
                update tenants
                set settings = coalesce(settings, '{}'::jsonb) || jsonb_build_object(
                    'welcome_email_status', cast(:status as text),
                    'welcome_email_recipient', cast(:recipient as text),
                    'welcome_email_updated_at', cast(now() as text)
                )
                where id=cast(:tenant_id as uuid)
                """
            ),
            {
                "tenant_id": str(tenant.id),
                "status": "SENT" if result.delivered else "FAILED",
                "recipient": admin_email,
            },
        )
