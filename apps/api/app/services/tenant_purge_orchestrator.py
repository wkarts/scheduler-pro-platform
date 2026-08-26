from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.tenant_lifecycle_service import TenantLifecycleService


class TenantPurgeOrchestrator:
    """Coordena o purge definitivo sem criar um segundo motor destrutivo.

    A remoção de banco, armazenamento, DNS e metadados continua sendo executada
    exclusivamente por TenantLifecycleService. Este serviço acrescenta somente a
    trilha independente, retomada e remoção final do registro operacional.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.lifecycle = TenantLifecycleService(session)

    async def _tenant_snapshot(self, tenant_id: str) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    select id::text as id, name, slug, status
                    from tenants
                    where id=cast(:tenant_id as uuid)
                    limit 1
                    """
                ),
                {"tenant_id": tenant_id},
            )
        ).mappings().first()
        if row is None:
            # Uma repetição depois da conclusão é idempotente desde que exista a
            # auditoria independente da mesma conta/correlation id.
            raise APIError("TENANT_NOT_FOUND", "Empresa não encontrada.", 404)
        return dict(row)

    async def _audit_id(
        self,
        *,
        snapshot: dict[str, Any],
        actor_user_id: str,
        correlation_id: str,
    ) -> str:
        existing = await self.session.scalar(
            text(
                """
                select id::text
                from tenant_purge_audits
                where original_tenant_id=cast(:tenant_id as uuid)
                  and correlation_id=:correlation_id
                limit 1
                """
            ),
            {
                "tenant_id": snapshot["id"],
                "correlation_id": correlation_id,
            },
        )
        if existing:
            return str(existing)
        audit_id = await self.session.scalar(
            text(
                """
                insert into tenant_purge_audits(
                    original_tenant_id, original_name, original_slug,
                    actor_user_id, correlation_id, status,
                    resources_removed, resources_pending, failures
                ) values(
                    cast(:tenant_id as uuid), :name, :slug,
                    cast(:actor_user_id as uuid), :correlation_id, 'PENDING',
                    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb
                )
                returning id::text
                """
            ),
            {
                "tenant_id": snapshot["id"],
                "name": snapshot["name"],
                "slug": snapshot["slug"],
                "actor_user_id": actor_user_id,
                "correlation_id": correlation_id,
            },
        )
        await self.session.commit()
        return str(audit_id)

    async def _update_audit(
        self,
        audit_id: str,
        *,
        status: str,
        removed: list[Any] | None = None,
        pending: list[Any] | None = None,
        failures: list[Any] | None = None,
        completed: bool = False,
    ) -> None:
        await self.session.execute(
            text(
                """
                update tenant_purge_audits
                set status=:status,
                    resources_removed=cast(:removed as jsonb),
                    resources_pending=cast(:pending as jsonb),
                    failures=cast(:failures as jsonb),
                    completed_at=case when :completed then now() else null end
                where id=cast(:id as uuid)
                """
            ),
            {
                "id": audit_id,
                "status": status,
                "removed": json.dumps(removed or [], ensure_ascii=False, default=str),
                "pending": json.dumps(pending or [], ensure_ascii=False, default=str),
                "failures": json.dumps(failures or [], ensure_ascii=False, default=str),
                "completed": completed,
            },
        )
        await self.session.commit()

    @staticmethod
    def _removed_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"resource": "Domínios e DNS", "records_removed": result.get("dns_records_removed", 0)},
            {"resource": "Armazenamento", "removed": True},
            {"resource": "Banco de Dados", "removed": True},
            {"resource": "Credenciais", "removed": True},
            {"resource": "Sessões e acessos", "removed": True},
            {"resource": "Configurações e branding", "removed": True},
            {"resource": "Páginas, versões, builds e artefatos", "removed": True},
            {"resource": "Provisionamento e associações operacionais", "rows_removed": result.get("tenant_metadata_rows_removed", 0)},
        ]

    async def _finish_operational_deletion(self, tenant_id: str) -> int:
        """Remove o que mantém a conta operacional e, por último, o tenant.

        As deleções são intencionalmente idempotentes. Se surgir uma FK nova no
        futuro, a transação falha inteira, o tenant permanece retomável e a
        auditoria registra PARTIAL em vez de mascarar o problema.
        """
        await self.session.execute(
            text(
                "delete from tenant_resource_boundaries "
                "where tenant_id=cast(:tenant_id as uuid)"
            ),
            {"tenant_id": tenant_id},
        )
        result = await self.session.execute(
            text("delete from tenants where id=cast(:tenant_id as uuid)"),
            {"tenant_id": tenant_id},
        )
        if result.rowcount != 1:
            raise APIError(
                "TENANT_PURGE_FINALIZE_FAILED",
                "A empresa não pôde ser removida do cadastro operacional.",
                409,
            )
        await self.session.commit()
        return int(result.rowcount or 0)

    async def purge_permanently(
        self,
        tenant_id: str,
        *,
        actor_user_id: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        # Idempotência após sucesso: o registro operacional já não existe, mas o
        # correlation id devolve a conclusão registrada.
        existing_audit = (
            await self.session.execute(
                text(
                    """
                    select id::text, original_name, original_slug, status,
                           resources_removed, resources_pending, failures,
                           completed_at
                    from tenant_purge_audits
                    where original_tenant_id=cast(:tenant_id as uuid)
                      and correlation_id=:correlation_id
                    limit 1
                    """
                ),
                {"tenant_id": tenant_id, "correlation_id": correlation_id},
            )
        ).mappings().first()
        tenant_exists = bool(
            await self.session.scalar(
                text("select exists(select 1 from tenants where id=cast(:tenant_id as uuid))"),
                {"tenant_id": tenant_id},
            )
        )
        if existing_audit and not tenant_exists and str(existing_audit["status"]) == "SUCCESS":
            return {
                "tenant_id": tenant_id,
                "name": existing_audit["original_name"],
                "slug": existing_audit["original_slug"],
                "status": "SUCCESS",
                "audit_id": existing_audit["id"],
                "resources_removed": existing_audit["resources_removed"],
                "idempotent_replay": True,
            }

        snapshot = await self._tenant_snapshot(tenant_id)
        audit_id = await self._audit_id(
            snapshot=snapshot,
            actor_user_id=actor_user_id,
            correlation_id=correlation_id,
        )
        await self._update_audit(audit_id, status="RUNNING")

        removed: list[Any] = []
        try:
            # O nome é passado somente porque este é o contrato histórico do
            # motor existente. A nova rota valida slug + confirmação de risco.
            result = await self.lifecycle.purge(
                tenant_id,
                str(snapshot["name"]),
                force=False,
            )
            removed = self._removed_from_result(result)
        except APIError as exc:
            await self.session.rollback()
            details = exc.details if isinstance(exc.details, dict) else {}
            warnings = details.get("warnings", []) if isinstance(details, dict) else []
            pending = warnings if isinstance(warnings, list) else [warnings]
            failures = [
                {
                    "code": exc.code,
                    "message": exc.message,
                    "details": details,
                }
            ]
            await self._update_audit(
                audit_id,
                status="PARTIAL",
                removed=removed,
                pending=pending,
                failures=failures,
            )
            raise APIError(
                "TENANT_PURGE_PARTIAL",
                "A exclusão definitiva ficou parcial e pode ser retomada com segurança.",
                424,
                {
                    "audit_id": audit_id,
                    "correlation_id": correlation_id,
                    "pending": pending,
                },
            ) from exc
        except Exception as exc:
            await self.session.rollback()
            await self._update_audit(
                audit_id,
                status="PARTIAL",
                removed=removed,
                pending=["Recursos operacionais da empresa"],
                failures=[{"type": type(exc).__name__, "message": str(exc)[:1000]}],
            )
            raise

        try:
            await self._finish_operational_deletion(tenant_id)
        except Exception as exc:
            await self.session.rollback()
            await self._update_audit(
                audit_id,
                status="PARTIAL",
                removed=removed,
                pending=["Registro operacional da empresa"],
                failures=[{"type": type(exc).__name__, "message": str(exc)[:1000]}],
            )
            raise APIError(
                "TENANT_PURGE_PARTIAL",
                "Os recursos foram removidos, mas a finalização cadastral ficou pendente. A operação pode ser repetida.",
                409,
                {
                    "audit_id": audit_id,
                    "correlation_id": correlation_id,
                    "pending": ["Registro operacional da empresa"],
                },
            ) from exc

        await self._update_audit(
            audit_id,
            status="SUCCESS",
            removed=removed,
            pending=[],
            failures=[],
            completed=True,
        )
        return {
            "tenant_id": tenant_id,
            "name": snapshot["name"],
            "slug": snapshot["slug"],
            "status": "SUCCESS",
            "audit_id": audit_id,
            "correlation_id": correlation_id,
            "resources_removed": removed,
            "operational_record_removed": True,
            "idempotent_replay": False,
        }
