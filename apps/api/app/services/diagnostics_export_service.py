from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import tenant_session
from app.services.docker_console_service import DockerConsoleService
from app.services.observability_service import ObservabilityService
from app.services.tenant_resolver import TenantResolver

_REDACT_KEYS = re.compile(
    r"(password|passwd|secret|token|authorization|cookie|api[_-]?key|private[_-]?key)",
    re.IGNORECASE,
)
_REDACT_TEXT_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;\"']+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+\-/=]+"),
    re.compile(
        r"(?i)((?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*)[^\s,;\"']+"
    ),
]


class DiagnosticsExportService:
    """Build a redacted support bundle without exporting application secrets.

    The bundle intentionally contains operational state and logs, but never reads
    `.env`, certificate private keys or sealed tenant credentials.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.docker = DockerConsoleService()
        self.errors: list[dict[str, str]] = []
        self.notes: list[str] = []

    @staticmethod
    def _json_default(value: Any) -> str:
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        return str(value)

    @classmethod
    def _redact_text(cls, value: str) -> str:
        clean = value
        for pattern in _REDACT_TEXT_PATTERNS:
            clean = pattern.sub(r"\1[REDACTED]", clean)
        return clean

    @classmethod
    def _redact(cls, value: Any) -> Any:
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                if _REDACT_KEYS.search(str(key)):
                    result[str(key)] = "[REDACTED]"
                else:
                    result[str(key)] = cls._redact(item)
            return result
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        if isinstance(value, tuple):
            return [cls._redact(item) for item in value]
        if isinstance(value, str):
            return cls._redact_text(value)
        return value

    @classmethod
    def _json_bytes(cls, value: Any) -> bytes:
        return (
            json.dumps(
                cls._redact(value),
                ensure_ascii=False,
                indent=2,
                default=cls._json_default,
            )
            + "\n"
        ).encode("utf-8")

    @classmethod
    def _jsonl_bytes(cls, rows: list[dict[str, Any]]) -> bytes:
        return (
            "\n".join(
                json.dumps(
                    cls._redact(row),
                    ensure_ascii=False,
                    default=cls._json_default,
                )
                for row in rows
            )
            + ("\n" if rows else "")
        ).encode("utf-8")

    @staticmethod
    def _scope_sql(
        *,
        tenant_id: str | None,
        allowed_tenant_ids: set[str] | None,
        column: str,
    ) -> tuple[str, dict[str, Any]]:
        if tenant_id:
            return f" and {column}=cast(:tenant_id as uuid)", {"tenant_id": tenant_id}
        if allowed_tenant_ids is None:
            return "", {}
        if not allowed_tenant_ids:
            return " and false", {}
        return (
            f" and {column}=any(cast(:allowed_tenant_ids as uuid[]))",
            {"allowed_tenant_ids": sorted(allowed_tenant_ids)},
        )

    async def _query_rows(
        self,
        name: str,
        statement: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            rows = (
                await self.session.execute(text(statement), params or {})
            ).mappings().all()
            return [dict(row) for row in rows]
        except Exception as exc:  # noqa: BLE001 - bundle must remain downloadable
            await self.session.rollback()
            self.errors.append(
                {"section": name, "error": f"{type(exc).__name__}: {exc}"}
            )
            return []

    async def _platform_state(
        self,
        *,
        tenant_id: str | None,
        allowed_tenant_ids: set[str] | None,
    ) -> dict[str, list[dict[str, Any]]]:
        tenant_scope, tenant_params = self._scope_sql(
            tenant_id=tenant_id,
            allowed_tenant_ids=allowed_tenant_ids,
            column="t.id",
        )
        domain_scope, domain_params = self._scope_sql(
            tenant_id=tenant_id,
            allowed_tenant_ids=allowed_tenant_ids,
            column="d.tenant_id",
        )
        job_scope, job_params = self._scope_sql(
            tenant_id=tenant_id,
            allowed_tenant_ids=allowed_tenant_ids,
            column="pj.tenant_id",
        )

        tenants = await self._query_rows(
            "tenants",
            f"""
            select t.id::text, t.name, t.slug, t.status, t.timezone, t.created_at,
                   td.database_name, td.database_user,
                   ts.bucket as storage_bucket,
                   d.hostname as primary_hostname
            from tenants t
            left join tenant_databases td on td.tenant_id=t.id
            left join tenant_storage ts on ts.tenant_id=t.id
            left join domains d on d.tenant_id=t.id and d.is_primary=true
            where true {tenant_scope}
            order by t.created_at desc
            """,
            tenant_params,
        )
        domains = await self._query_rows(
            "domains",
            f"""
            select d.id::text, d.tenant_id::text, t.name as tenant_name,
                   d.hostname, d.is_primary, d.is_temporary, d.status, d.validation
            from domains d
            join tenants t on t.id=d.tenant_id
            where true {domain_scope}
            order by d.id::text
            """,
            domain_params,
        )
        jobs = await self._query_rows(
            "provisioning_jobs",
            f"""
            select pj.id::text, pj.tenant_id::text, t.name as tenant_name,
                   t.slug, pj.status, pj.correlation_id, pj.created_at, pj.updated_at
            from provisioning_jobs pj
            join tenants t on t.id=pj.tenant_id
            where true {job_scope}
            order by pj.created_at desc
            """,
            job_params,
        )
        steps = await self._query_rows(
            "provisioning_steps",
            f"""
            select ps.id::text, ps.job_id::text, pj.tenant_id::text,
                   ps.name, ps.status, ps.error
            from provisioning_steps ps
            join provisioning_jobs pj on pj.id=ps.job_id
            where true {job_scope}
            order by pj.created_at desc, ps.id::text
            """,
            job_params,
        )

        if tenant_id is None and allowed_tenant_ids is None:
            audit = await self._query_rows(
                "platform_audit",
                """
                select a.id::text, a.user_id::text, u.email,
                       a.action, a.result, a.ip_address, a.correlation_id,
                       a.metadata, a.created_at
                from platform_audit_logs a
                left join platform_users u on u.id=a.user_id
                order by a.created_at desc
                limit 100000
                """,
            )
        else:
            audit = []
            self.notes.append(
                "platform_audit omitido porque a tabela não possui tenant_id; "
                "auditoria do tenant continua incluída no banco isolado."
            )

        boundaries = await self._query_rows(
            "tenant_boundaries",
            f"""
            select rb.tenant_id::text, t.name as tenant_name, t.slug,
                   rb.database_name, rb.database_user, rb.storage_bucket,
                   rb.storage_prefix, rb.artifact_prefix, rb.log_retention_days,
                   rb.isolation_status, rb.details, rb.created_at, rb.updated_at
            from tenant_resource_boundaries rb
            join tenants t on t.id=rb.tenant_id
            where true {tenant_scope}
            order by t.created_at desc
            """,
            tenant_params,
        )
        return {
            "tenants": tenants,
            "domains": domains,
            "provisioning_jobs": jobs,
            "provisioning_steps": steps,
            "platform_audit": audit,
            "tenant_boundaries": boundaries,
        }

    async def _platform_logs(
        self,
        *,
        tenant_id: str | None,
        allowed_tenant_ids: set[str] | None,
    ) -> list[dict[str, Any]]:
        try:
            rows = await ObservabilityService(self.session).list_platform_logs(
                tenant_filter=tenant_id,
                limit=100000,
            )
        except Exception as exc:  # noqa: BLE001
            await self.session.rollback()
            self.errors.append(
                {
                    "section": "platform_logs",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return []
        if tenant_id or allowed_tenant_ids is None:
            return rows
        return [
            row
            for row in rows
            if row.get("tenant_id") is None
            or str(row.get("tenant_id")) in allowed_tenant_ids
        ]

    async def _tenant_database_diagnostics(
        self,
        tenants: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        resolver = TenantResolver(self.session)
        for tenant in tenants:
            tenant_id = str(tenant.get("id") or "")
            if not tenant_id:
                continue
            slug = str(tenant.get("slug") or tenant_id)
            section: dict[str, Any] = {"tenant_id": tenant_id, "slug": slug}
            try:
                context = await resolver.resolve_by_id(tenant_id, require_active=False)
                async for tenant_db in tenant_session(context):
                    service = ObservabilityService(tenant_db)
                    section["logs"] = await service.list_tenant_logs(limit=50000)
                    audit_rows = (
                        await tenant_db.execute(
                            text(
                                """
                                select a.id::text, a.user_id::text, u.email, a.action,
                                       a.result, a.ip_address, a.correlation_id,
                                       a.metadata, a.created_at
                                from audit_logs a
                                left join users u on u.id=a.user_id
                                order by a.created_at desc
                                limit 50000
                                """
                            )
                        )
                    ).mappings().all()
                    section["audit"] = [dict(row) for row in audit_rows]
                    break
            except Exception as exc:  # noqa: BLE001 - failed tenants are expected
                section["error"] = f"{type(exc).__name__}: {exc}"
            result[slug] = section
        return result

    async def _docker_diagnostics(self) -> dict[str, Any]:
        result: dict[str, Any] = {"containers": [], "logs": {}}
        try:
            containers = await self.docker.containers()
            result["containers"] = containers
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"{type(exc).__name__}: {exc}"
            self.errors.append(
                {"section": "docker_containers", "error": result["error"]}
            )
            return result

        for container in containers:
            identifier = str(container.get("service") or container.get("name") or "")
            if not identifier:
                continue
            try:
                payload = await self.docker.logs(identifier, all_lines=True)
                result["logs"][identifier] = payload
            except Exception as exc:  # noqa: BLE001
                message = f"{type(exc).__name__}: {exc}"
                result["logs"][identifier] = {"error": message}
                self.errors.append(
                    {"section": f"docker:{identifier}", "error": message}
                )
        return result

    async def build_bundle(
        self,
        *,
        tenant_id: str | None = None,
        allowed_tenant_ids: set[str] | None = None,
    ) -> tuple[bytes, str]:
        generated_at = datetime.now(UTC)
        platform_logs = await self._platform_logs(
            tenant_id=tenant_id,
            allowed_tenant_ids=allowed_tenant_ids,
        )
        state = await self._platform_state(
            tenant_id=tenant_id,
            allowed_tenant_ids=allowed_tenant_ids,
        )
        tenant_diagnostics = await self._tenant_database_diagnostics(state["tenants"])
        docker = await self._docker_diagnostics()
        frontend_logs = [
            row for row in platform_logs if row.get("source") == "frontend"
        ]

        manifest = {
            "product": "Scheduler Pro",
            "generated_at": generated_at.isoformat(),
            "tenant_filter": tenant_id,
            "platform_log_count": len(platform_logs),
            "frontend_log_count": len(frontend_logs),
            "tenant_count": len(state["tenants"]),
            "docker_container_count": len(docker.get("containers", [])),
            "notes": self.notes,
            "errors": self.errors,
            "security": {
                "secrets_redacted": True,
                "env_exported": False,
                "private_keys_exported": False,
                "sealed_credentials_exported": False,
            },
        }

        output = io.BytesIO()
        with zipfile.ZipFile(
            output,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.writestr("manifest.json", self._json_bytes(manifest))
            archive.writestr(
                "README.txt",
                (
                    "Scheduler Pro - pacote de diagnóstico\n\n"
                    "Inclui logs estruturados, auditoria disponível, provisionamento, "
                    "domínios, isolamento, bancos dos tenants acessíveis e todo o "
                    "stdout/stderr ainda retido pelo Docker para os containers do projeto.\n"
                    "Eventos de navegador capturados pelo Admin aparecem em "
                    "frontend/browser.jsonl.\n\n"
                    "Segredos conhecidos são redigidos. O pacote não lê .env, "
                    "chaves privadas TLS nem credenciais seladas.\n"
                ).encode("utf-8"),
            )
            archive.writestr(
                "platform/logs.jsonl",
                self._jsonl_bytes(platform_logs),
            )
            archive.writestr(
                "frontend/browser.jsonl",
                self._jsonl_bytes(frontend_logs),
            )
            for name, rows in state.items():
                archive.writestr(
                    f"platform/{name}.json",
                    self._json_bytes(rows),
                )
            for slug, data in tenant_diagnostics.items():
                archive.writestr(
                    f"tenants/{slug}/diagnostics.json",
                    self._json_bytes(data),
                )
            archive.writestr(
                "docker/containers.json",
                self._json_bytes(docker.get("containers", [])),
            )
            for identifier, payload in dict(docker.get("logs", {})).items():
                safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", identifier)[:120] or "container"
                entries = (
                    payload.get("entries", [])
                    if isinstance(payload, dict)
                    else []
                )
                archive.writestr(
                    f"docker/{safe}.jsonl",
                    self._jsonl_bytes(entries),
                )
                if isinstance(payload, dict) and payload.get("error"):
                    archive.writestr(
                        f"docker/{safe}.error.txt",
                        self._redact_text(str(payload["error"])).encode("utf-8"),
                    )
            if self.errors:
                archive.writestr("errors.json", self._json_bytes(self.errors))

        filename = (
            f"scheduler-pro-diagnostics-"
            f"{generated_at.strftime('%Y%m%d-%H%M%SZ')}.zip"
        )
        return output.getvalue(), filename
