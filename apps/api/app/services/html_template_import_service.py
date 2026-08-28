from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.global_template_service import GlobalTemplateService
from app.services.html_template_contract import HtmlTemplateContract

VALID_SCOPES = {"GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL", "PLATFORM_DEFAULT"}


class HtmlTemplateImportService:
    """Importa famílias HTML na biblioteca global versionada.

    O HTML é preservado integralmente dentro do envelope interno e cada
    superfície continua usando a infraestrutura já existente de versões,
    escopo e aplicação por cliente.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.templates = GlobalTemplateService(session)

    async def _existing(self, surface: str, key: str) -> str | None:
        value = await self.session.scalar(
            text(
                "select id::text from global_content_templates "
                "where surface=:surface and key=:key limit 1"
            ),
            {"surface": surface, "key": key},
        )
        return str(value) if value else None

    @staticmethod
    def _scope(value: str) -> str:
        scope = value.strip().upper()
        if scope not in VALID_SCOPES:
            raise APIError("TEMPLATE_SCOPE_INVALID", "Escopo de modelo inválido.", 422)
        return scope

    async def import_pair(
        self,
        *,
        landing_html: str | None,
        booking_html: str | None,
        login_html: str | None = None,
        name: str,
        description: str | None,
        segment: str | None,
        actor: str | None,
        scope: str = "INTERNAL",
        exclusive_tenant_id: str | None = None,
        selected_tenant_ids: list[str] | None = None,
        default_for_new_tenants: bool = False,
        publish: bool = False,
        update_existing: bool = True,
    ) -> dict[str, Any]:
        validation = HtmlTemplateContract.ensure_family(
            landing_html=landing_html,
            booking_html=booking_html,
            login_html=login_html,
        )
        key = str(validation["template_key"])
        clean_name = name.strip()
        if len(clean_name) < 2 or len(clean_name) > 180:
            raise APIError("GLOBAL_TEMPLATE_NAME_INVALID", "Nome do modelo inválido.", 422)
        normalized_scope = self._scope(scope)
        storage_scope = "GLOBAL" if normalized_scope == "PLATFORM_DEFAULT" else normalized_scope
        exclusive = str(exclusive_tenant_id or "").strip() or None
        selected = [str(item) for item in selected_tenant_ids or []]
        if storage_scope == "EXCLUSIVE" and not exclusive:
            raise APIError(
                "GLOBAL_TEMPLATE_TENANT_REQUIRED",
                "Escolha o cliente exclusivo antes de importar.",
                422,
            )
        if storage_scope == "SELECTED" and not selected:
            raise APIError(
                "GLOBAL_TEMPLATE_SELECTED_TENANTS_REQUIRED",
                "Escolha ao menos um cliente para este modelo.",
                422,
            )

        source: list[tuple[str, str, str]] = []
        if landing_html:
            source.append(("LANDING", landing_html, clean_name))
        if booking_html:
            source.append(("BOOKING", booking_html, f"{clean_name} — Agendamento"))
        if login_html:
            source.append(("LOGIN", login_html, f"{clean_name} — Login"))

        results: list[dict[str, Any]] = []
        for surface, html_document, surface_name in source:
            content = HtmlTemplateContract.wrapper(
                html_document,
                expected_surface=surface,
            )
            existing_id = await self._existing(surface, key)
            metadata = {
                "name": surface_name,
                "description": description.strip() if description and description.strip() else None,
                "segment": segment.strip() if segment and segment.strip() else None,
                "scope": storage_scope,
                "default_for_new_tenants": bool(default_for_new_tenants),
                "exclusive_tenant_id": exclusive if storage_scope == "EXCLUSIVE" else None,
                "selected_tenant_ids": selected if storage_scope == "SELECTED" else [],
            }
            changelog = "Importação HTML pelo Control Plane"
            if existing_id:
                if not update_existing:
                    raise APIError(
                        "GLOBAL_TEMPLATE_ALREADY_EXISTS",
                        f"Já existe um modelo {surface} com a chave {key}.",
                        409,
                    )
                current = await self.templates.get(existing_id)
                await self.templates.update_metadata(
                    existing_id,
                    {
                        **metadata,
                        "status": "PUBLISHED" if publish else current["status"],
                    },
                    actor=actor,
                )
                version = await self.templates.create_version(
                    existing_id,
                    content,
                    changelog=changelog,
                    actor=actor,
                    publish=publish,
                )
                results.append(
                    {
                        "surface": surface,
                        "template_id": existing_id,
                        "key": key,
                        "version_number": int(version["version_number"]),
                        "created": False,
                        "published": publish,
                    }
                )
                continue

            created = await self.templates.create(
                {
                    "surface": surface,
                    "key": key,
                    **metadata,
                    "status": "PUBLISHED" if publish else "DRAFT",
                    "content": content,
                    "changelog": changelog,
                },
                actor=actor,
            )
            results.append(
                {
                    "surface": surface,
                    "template_id": str(created["id"]),
                    "key": key,
                    "version_number": int(created["latest_version"] or 1),
                    "created": True,
                    "published": publish,
                }
            )

        return {
            "contract": HtmlTemplateContract.descriptor()["schema"],
            "template_key": key,
            "name": clean_name,
            "scope": normalized_scope,
            "storage_scope": storage_scope,
            "validation": validation,
            "templates": results,
            "automatic_tenant_update": False,
        }
