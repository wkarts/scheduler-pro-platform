import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any

import asyncpg
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import TenantStatus
from app.core.errors import APIError
from app.services.cloudflare_service import CloudflareService
from app.services.observability_service import ObservabilityService

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifier(value: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise APIError("TENANT_RESOURCE_IDENTIFIER_INVALID", "Identificador de recurso inválido.", 500)
    return f'"{value}"'


class TenantLifecycleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.logs = ObservabilityService(session)
        self.cloudflare = CloudflareService(
            settings.cloudflare_api_token,
            settings.cloudflare_zone_id,
            api_base_url=settings.cloudflare_api_base_url,
            dry_run=settings.cloudflare_dry_run,
            custom_hostname_origin=settings.cloudflare_custom_hostname_origin,
        )

    async def _tenant(self, tenant_id: str) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    select t.id::text, t.name, t.slug, t.status, t.settings,
                           td.database_name, td.database_user,
                           ts.bucket
                    from tenants t
                    left join tenant_databases td on td.tenant_id=t.id
                    left join tenant_storage ts on ts.tenant_id=t.id
                    where t.id=cast(:id as uuid)
                    limit 1
                    """
                ),
                {"id": tenant_id},
            )
        ).mappings().first()
        if row is None:
            raise APIError("TENANT_NOT_FOUND", "Tenant não encontrado.", 404)
        return dict(row)

    async def _audit(
        self,
        actor_id: str,
        action: str,
        tenant: dict[str, Any],
        *,
        result: str = "SUCCESS",
        details: dict[str, Any] | None = None,
    ) -> None:
        metadata = {
            "tenant_id": tenant["id"],
            "tenant_name": tenant["name"],
            "tenant_slug": tenant["slug"],
            **(details or {}),
        }
        await self.session.execute(
            text(
                """
                insert into platform_audit_logs(user_id, action, result, metadata)
                values(cast(:actor as uuid), :action, :result, cast(:metadata as jsonb))
                """
            ),
            {
                "actor": actor_id,
                "action": action,
                "result": result,
                "metadata": json.dumps(metadata, ensure_ascii=False),
            },
        )

    async def suspend(self, tenant_id: str, actor_id: str) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        if tenant["status"] == TenantStatus.deleted.value:
            raise APIError("TENANT_DELETED", "Tenant excluído; restaure antes de suspender.", 409)
        await self.session.execute(
            text("update tenants set status='SUSPENDED' where id=cast(:id as uuid)"),
            {"id": tenant_id},
        )
        await self.session.execute(
            text(
                """
                update tenant_resource_boundaries
                set isolation_status='SUSPENDED', updated_at=now()
                where tenant_id=cast(:id as uuid)
                """
            ),
            {"id": tenant_id},
        )
        await self._audit(actor_id, "tenant.suspend", tenant)
        await self.logs.record_platform_log(
            tenant_id=tenant_id,
            source="audit",
            service="tenant-lifecycle",
            event="tenant_suspended",
            message="Tenant suspenso pelo Control Plane.",
            actor=actor_id,
        )
        await self.session.commit()
        return {"tenant_id": tenant_id, "status": TenantStatus.suspended.value}

    async def restore(self, tenant_id: str, actor_id: str) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        stored = tenant.get("settings") or {}
        if isinstance(stored, dict) and stored.get("purged"):
            raise APIError("TENANT_PURGED", "Tenant expurgado não pode ser restaurado.", 409)
        if not tenant.get("database_name") or not tenant.get("bucket"):
            raise APIError("TENANT_RESOURCES_MISSING", "Recursos do tenant não estão disponíveis para restauração.", 409)
        await self.session.execute(
            text("update tenants set status='ACTIVE' where id=cast(:id as uuid)"),
            {"id": tenant_id},
        )
        await self.session.execute(
            text(
                """
                update tenant_resource_boundaries
                set isolation_status='ACTIVE', updated_at=now()
                where tenant_id=cast(:id as uuid)
                """
            ),
            {"id": tenant_id},
        )
        await self._audit(actor_id, "tenant.restore", tenant)
        await self.logs.record_platform_log(
            tenant_id=tenant_id,
            source="audit",
            service="tenant-lifecycle",
            event="tenant_restored",
            message="Tenant restaurado pelo Control Plane.",
            actor=actor_id,
        )
        await self.session.commit()
        return {"tenant_id": tenant_id, "status": TenantStatus.active.value}

    async def soft_delete(self, tenant_id: str, actor_id: str) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        if tenant["status"] == TenantStatus.deleted.value:
            return {"tenant_id": tenant_id, "status": TenantStatus.deleted.value, "already_deleted": True}
        deleted_at = datetime.now(UTC).isoformat()
        await self.session.execute(
            text(
                """
                update tenants
                set status='DELETED',
                    settings=coalesce(settings,'{}'::jsonb) || jsonb_build_object('deleted_at', :deleted_at)
                where id=cast(:id as uuid)
                """
            ),
            {"id": tenant_id, "deleted_at": deleted_at},
        )
        await self.session.execute(
            text(
                """
                update tenant_resource_boundaries
                set isolation_status='DELETED', updated_at=now()
                where tenant_id=cast(:id as uuid)
                """
            ),
            {"id": tenant_id},
        )
        await self._audit(actor_id, "tenant.delete", tenant, details={"soft_delete": True})
        await self.logs.record_platform_log(
            tenant_id=tenant_id,
            source="audit",
            service="tenant-lifecycle",
            event="tenant_deleted",
            message="Tenant excluído logicamente; recursos preservados para recuperação.",
            actor=actor_id,
        )
        await self.session.commit()
        return {"tenant_id": tenant_id, "status": TenantStatus.deleted.value, "recoverable": True}

    async def _cleanup_cloudflare(self, tenant_id: str) -> list[str]:
        warnings: list[str] = []
        rows = (
            await self.session.execute(
                text(
                    """
                    select id::text, hostname, is_temporary, validation
                    from domains where tenant_id=cast(:id as uuid)
                    """
                ),
                {"id": tenant_id},
            )
        ).mappings().all()
        for row in rows:
            try:
                if row["is_temporary"]:
                    lookup = await self.cloudflare.list_dns_records(row["hostname"])
                    result = lookup.get("result")
                    if isinstance(result, list):
                        for record in result:
                            if isinstance(record, dict) and record.get("id"):
                                await self.cloudflare.delete_dns_record(str(record["id"]))
                else:
                    validation = row["validation"] if isinstance(row["validation"], dict) else {}
                    custom_id = validation.get("custom_hostname_id")
                    if custom_id:
                        await self.cloudflare.delete_custom_hostname(str(custom_id))
            except Exception as exc:  # noqa: BLE001 - purge reports every remote cleanup failure
                warnings.append(f"Cloudflare {row['hostname']}: {exc}")
        return warnings

    @staticmethod
    def _empty_bucket(bucket: str) -> None:
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        try:
            paginator = client.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=bucket):
                objects = [
                    {"Key": item["Key"], "VersionId": item["VersionId"]}
                    for item in [*(page.get("Versions") or []), *(page.get("DeleteMarkers") or [])]
                ]
                for offset in range(0, len(objects), 1000):
                    client.delete_objects(Bucket=bucket, Delete={"Objects": objects[offset : offset + 1000], "Quiet": True})
        except (ClientError, BotoCoreError):
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket):
                objects = [{"Key": item["Key"]} for item in page.get("Contents") or []]
                for offset in range(0, len(objects), 1000):
                    client.delete_objects(Bucket=bucket, Delete={"Objects": objects[offset : offset + 1000], "Quiet": True})
        client.delete_bucket(Bucket=bucket)

    async def _drop_database(self, database_name: str, database_user: str) -> None:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_admin_user,
            password=settings.postgres_admin_password,
            database=settings.postgres_db,
        )
        try:
            await conn.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity where datname=$1 and pid<>pg_backend_pid()",
                database_name,
            )
            await conn.execute(f"drop database if exists {_identifier(database_name)}")
            await conn.execute(f"drop role if exists {_identifier(database_user)}")
        finally:
            await conn.close()

    async def purge(
        self,
        tenant_id: str,
        confirmation: str,
        actor_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        if confirmation.strip() != tenant["slug"]:
            raise APIError(
                "TENANT_PURGE_CONFIRMATION_INVALID",
                "Confirmação inválida. Informe exatamente o código do tenant.",
                400,
                {"expected": tenant["slug"]},
            )
        if isinstance(tenant.get("settings"), dict) and tenant["settings"].get("purged"):
            return {"tenant_id": tenant_id, "status": TenantStatus.deleted.value, "purged": True, "already_purged": True}

        await self.session.execute(
            text("update tenants set status='DELETING' where id=cast(:id as uuid)"),
            {"id": tenant_id},
        )
        await self.session.commit()

        warnings = await self._cleanup_cloudflare(tenant_id)
        bucket = tenant.get("bucket")
        if bucket:
            try:
                await asyncio.to_thread(self._empty_bucket, str(bucket))
            except (BotoCoreError, ClientError, OSError) as exc:
                warnings.append(f"Storage {bucket}: {exc}")
        database_name = tenant.get("database_name")
        database_user = tenant.get("database_user")
        if database_name and database_user:
            try:
                await self._drop_database(str(database_name), str(database_user))
            except (asyncpg.PostgresError, OSError, APIError) as exc:
                warnings.append(f"PostgreSQL {database_name}: {exc}")

        if warnings and not force:
            await self.session.execute(
                text("update tenants set status='DELETED' where id=cast(:id as uuid)"),
                {"id": tenant_id},
            )
            await self._audit(actor_id, "tenant.purge", tenant, result="BLOCKED", details={"warnings": warnings})
            await self.logs.record_platform_log(
                tenant_id=tenant_id,
                source="audit",
                service="tenant-lifecycle",
                level="ERROR",
                event="tenant_purge_blocked",
                message="Expurgo interrompido porque recursos externos não foram removidos integralmente.",
                actor=actor_id,
                details={"warnings": warnings},
            )
            await self.session.commit()
            raise APIError(
                "TENANT_PURGE_INCOMPLETE",
                "Expurgo interrompido: existem recursos externos pendentes. Corrija ou repita com force=true.",
                424,
                {"warnings": warnings},
            )

        for statement in [
            "delete from platform_user_tenants where tenant_id=cast(:id as uuid)",
            "delete from tenant_capabilities where tenant_id=cast(:id as uuid)",
            "delete from build_credentials where tenant_id=cast(:id as uuid)",
            "delete from build_requests where tenant_id=cast(:id as uuid)",
            "delete from build_profiles where tenant_id=cast(:id as uuid)",
            "delete from tenant_branding_assets where tenant_id=cast(:id as uuid)",
            "delete from tenant_branding_profiles where tenant_id=cast(:id as uuid)",
            "delete from provisioning_jobs where tenant_id=cast(:id as uuid)",
            "delete from domains where tenant_id=cast(:id as uuid)",
            "delete from tenant_storage where tenant_id=cast(:id as uuid)",
            "delete from tenant_databases where tenant_id=cast(:id as uuid)",
        ]:
            await self.session.execute(text(statement), {"id": tenant_id})

        purged_at = datetime.now(UTC).isoformat()
        await self.session.execute(
            text(
                """
                update tenants
                set status='DELETED',
                    settings=jsonb_build_object(
                        'purged', true,
                        'purged_at', :purged_at,
                        'original_slug', slug,
                        'original_name', name
                    )
                where id=cast(:id as uuid)
                """
            ),
            {"id": tenant_id, "purged_at": purged_at},
        )
        await self.session.execute(
            text(
                """
                update tenant_resource_boundaries
                set isolation_status='PURGED',
                    details=coalesce(details,'{}'::jsonb) || jsonb_build_object('purged_at', :purged_at),
                    updated_at=now()
                where tenant_id=cast(:id as uuid)
                """
            ),
            {"id": tenant_id, "purged_at": purged_at},
        )
        await self._audit(actor_id, "tenant.purge", tenant, details={"force": force, "warnings": warnings})
        await self.logs.record_platform_log(
            tenant_id=tenant_id,
            source="audit",
            service="tenant-lifecycle",
            level="WARNING",
            event="tenant_purged",
            message="Tenant expurgado; dados operacionais removidos e tombstone preservado.",
            actor=actor_id,
            details={"force": force, "warnings": warnings},
        )
        await self.session.commit()
        return {
            "tenant_id": tenant_id,
            "status": TenantStatus.deleted.value,
            "purged": True,
            "warnings": warnings,
        }
