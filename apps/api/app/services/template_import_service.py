from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.global_template_service import GlobalTemplateService
from app.services.template_contract import SCOPES, TemplateContract


class TemplateImportService:
    """Importa famílias de modelos sem tocar automaticamente nas páginas em uso."""

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
        if scope not in SCOPES:
            raise APIError("TEMPLATE_SCOPE_INVALID", "Escopo de modelo inválido.", 422)
        return scope

    async def import_bundle(
        self,
        bundle: dict[str, Any],
        *,
        actor: str | None,
        scope_override: str | None = None,
        exclusive_tenant_id: str | None = None,
        selected_tenant_ids: list[str] | None = None,
        publish: bool = False,
        update_existing: bool = True,
    ) -> dict[str, Any]:
        report = TemplateContract.ensure_package(bundle)
        package = bundle["package"]
        assert isinstance(package, dict)
        key = str(package["key"]).strip().lower()
        scope = self._scope(
            scope_override or str(package.get("scope") or "INTERNAL")
        )
        exclusive = (
            str(exclusive_tenant_id).strip()
            if exclusive_tenant_id
            else str(package.get("exclusive_tenant_id") or "").strip() or None
        )
        selected = [
            str(item)
            for item in (
                selected_tenant_ids
                if selected_tenant_ids is not None
                else package.get("selected_tenant_ids") or []
            )
        ]
        if scope == "EXCLUSIVE" and not exclusive:
            raise APIError(
                "GLOBAL_TEMPLATE_TENANT_REQUIRED",
                "Escolha o cliente exclusivo antes de importar.",
                422,
            )
        if scope == "SELECTED" and not selected:
            raise APIError(
                "GLOBAL_TEMPLATE_SELECTED_TENANTS_REQUIRED",
                "Escolha ao menos um cliente para o escopo selecionado.",
                422,
            )

        surfaces = package["surfaces"]
        assert isinstance(surfaces, dict)
        results: list[dict[str, Any]] = []
        for package_surface, surface in (("landing", "LANDING"), ("booking", "BOOKING")):
            content = surfaces.get(package_surface)
            if content is None:
                continue
            assert isinstance(content, dict)
            TemplateContract.ensure_content(surface, content, strict=True)
            existing_id = await self._existing(surface, key)
            metadata = {
                "name": (
                    str(package.get("landing_name") or package["name"])
                    if surface == "LANDING"
                    else str(package.get("booking_name") or f"{package['name']} — Agendamento")
                ),
                "description": str(package.get("description") or "").strip() or None,
                "segment": str(package.get("segment") or "").strip() or None,
                "scope": scope,
                "default_for_new_tenants": bool(package.get("default_for_new_tenants", False)),
                "exclusive_tenant_id": exclusive if scope == "EXCLUSIVE" else None,
                "selected_tenant_ids": selected if scope == "SELECTED" else [],
            }
            changelog = str(
                package.get("changelog")
                or f"Importado pelo {TemplateContract.descriptor()['name']}"
            )
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
                        "version_number": version["version_number"],
                        "created": False,
                        "published": bool(publish),
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
                    "published": bool(publish),
                }
            )

        return {
            "contract": TemplateContract.descriptor()["schema"],
            "key": key,
            "name": str(package["name"]),
            "scope": scope,
            "validation": report,
            "templates": results,
            "automatic_tenant_update": False,
        }
