from __future__ import annotations

import hashlib
from copy import deepcopy
from io import BytesIO
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.tenant_context import TenantContext
from app.services.experience_contract_service import ParsedExperience
from app.services.file_service import TenantFileService

SURFACES = {"LANDING": "/pagina", "BOOKING": "/agendar"}


class ExperienceService:
    def __init__(self, session: AsyncSession, context: TenantContext) -> None:
        self.session = session
        self.context = context

    @staticmethod
    def _surface(surface: str) -> str:
        value = str(surface).strip().upper()
        if value not in SURFACES:
            raise APIError("EXPERIENCE_SURFACE_INVALID", "Use LANDING ou BOOKING.", 422)
        return value

    async def _page(self, surface: str, *, create: bool = True) -> dict[str, Any] | None:
        normalized = self._surface(surface)
        row = (
            await self.session.execute(
                text("select * from tenant_public_pages where surface=:surface limit 1"),
                {"surface": normalized},
            )
        ).mappings().first()
        if row is not None or not create:
            return dict(row) if row is not None else None
        created = (
            await self.session.execute(
                text(
                    """
                    insert into tenant_public_pages(surface,route,enabled)
                    values(:surface,:route,true)
                    returning *
                    """
                ),
                {"surface": normalized, "route": SURFACES[normalized]},
            )
        ).mappings().one()
        await self.session.flush()
        return dict(created)

    async def ensure_default_experience(self) -> bool:
        count = int((await self.session.scalar(text("select count(*) from tenant_public_pages"))) or 0)
        if count:
            return False
        from app.services.builtin_template_package_service import (
            DEFAULT_TEMPLATE_KEY,
            builtin_template_archive,
        )
        from app.services.experience_contract_service import ExperienceContractService

        parsed = ExperienceContractService.parse_archive(
            builtin_template_archive(DEFAULT_TEMPLATE_KEY)
        )
        await self.import_package(parsed, actor=None)
        await self.publish("LANDING")
        await self.publish("BOOKING")
        return True

    async def summary(self) -> dict[str, Any]:
        await self.ensure_default_experience()
        rows = (
            await self.session.execute(
                text(
                    """
                    select id::text,surface,route,template_key,enabled,
                           draft_version_id::text,published_version_id::text,
                           theme,bindings,settings,updated_at
                    from tenant_public_pages
                    order by case surface when 'LANDING' then 1 else 2 end
                    """
                )
            )
        ).mappings().all()
        settings_rows = (
            await self.session.execute(
                text(
                    """
                    select key,value from tenant_settings
                    where key in ('experience_editor_level','experience_theme_apply_console','marketing_analytics','pwa_open_mode')
                    """
                )
            )
        ).mappings().all()
        settings = {str(row["key"]): row["value"] for row in settings_rows}
        return {
            "schema": "scheduler-pro-experience/v2",
            "pages": [dict(row) for row in rows],
            "editor": {"level": settings.get("experience_editor_level") or "basic"},
            "theme_apply_console": bool(settings.get("experience_theme_apply_console") or False),
            "marketing": settings.get("marketing_analytics") or {},
            "pwa_open_mode": settings.get("pwa_open_mode") or "AUTO",
        }

    async def document(self, surface: str, *, published: bool = False) -> dict[str, Any] | None:
        page = await self._page(surface, create=False)
        if page is None:
            return None
        version_id = page.get("published_version_id") if published else page.get("draft_version_id") or page.get("published_version_id")
        if not version_id:
            return {"page": page, "version": None}
        row = (
            await self.session.execute(
                text(
                    """
                    select id::text,version_number,html,metadata,bindings_values,theme,label,published,created_at
                    from tenant_public_page_versions
                    where id=cast(:id as uuid) and page_id=cast(:page_id as uuid)
                    limit 1
                    """
                ),
                {"id": str(version_id), "page_id": str(page["id"])},
            )
        ).mappings().first()
        return {"page": page, "version": dict(row) if row is not None else None}

    async def save_draft(
        self,
        surface: str,
        *,
        html: str,
        template_key: str | None,
        bindings_values: dict[str, Any] | None = None,
        theme: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        label: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        normalized = self._surface(surface)
        if not html.strip():
            raise APIError("EXPERIENCE_HTML_REQUIRED", "HTML da página é obrigatório.", 422)
        if len(html.encode("utf-8")) > 16 * 1024 * 1024:
            raise APIError("EXPERIENCE_HTML_TOO_LARGE", "HTML excede 16 MB após normalização.", 413)
        page = await self._page(normalized)
        assert page is not None
        version_number = int(
            (
                await self.session.scalar(
                    text("select coalesce(max(version_number),0)+1 from tenant_public_page_versions where page_id=cast(:id as uuid)"),
                    {"id": str(page["id"])},
                )
            )
            or 1
        )
        row = (
            await self.session.execute(
                text(
                    """
                    insert into tenant_public_page_versions(
                      page_id,version_number,html,metadata,bindings_values,theme,label,created_by
                    ) values(
                      cast(:page_id as uuid),:version_number,:html,cast(:metadata as jsonb),
                      cast(:bindings as jsonb),cast(:theme as jsonb),:label,
                      case when :actor='' then null else cast(:actor as uuid) end
                    )
                    returning id::text,version_number,created_at
                    """
                ),
                {
                    "page_id": str(page["id"]),
                    "version_number": version_number,
                    "html": html,
                    "metadata": __import__("json").dumps(metadata or {}),
                    "bindings": __import__("json").dumps(bindings_values or {}),
                    "theme": __import__("json").dumps(theme or {}),
                    "label": label,
                    "actor": actor or "",
                },
            )
        ).mappings().one()
        await self.session.execute(
            text(
                """
                update tenant_public_pages
                set draft_version_id=cast(:version_id as uuid),template_key=:template_key,
                    theme=cast(:theme as jsonb),updated_at=now()
                where id=cast(:page_id as uuid)
                """
            ),
            {
                "version_id": row["id"],
                "template_key": template_key,
                "theme": __import__("json").dumps(theme or {}),
                "page_id": str(page["id"]),
            },
        )
        await self.session.commit()
        return {"surface": normalized, "version_id": row["id"], "version_number": row["version_number"], "template_key": template_key}

    async def publish(self, surface: str, version_id: str | None = None) -> dict[str, Any]:
        page = await self._page(surface)
        assert page is not None
        target = version_id or str(page.get("draft_version_id") or "")
        if not target:
            raise APIError("EXPERIENCE_DRAFT_REQUIRED", "Salve um rascunho antes de publicar.", 409)
        exists = await self.session.scalar(
            text("select 1 from tenant_public_page_versions where id=cast(:id as uuid) and page_id=cast(:page_id as uuid)"),
            {"id": target, "page_id": str(page["id"])},
        )
        if exists is None:
            raise APIError("EXPERIENCE_VERSION_NOT_FOUND", "Versão não encontrada.", 404)
        await self.session.execute(text("update tenant_public_page_versions set published=false where page_id=cast(:page_id as uuid)"), {"page_id": str(page["id"])})
        await self.session.execute(text("update tenant_public_page_versions set published=true where id=cast(:id as uuid)"), {"id": target})
        await self.session.execute(
            text("update tenant_public_pages set published_version_id=cast(:id as uuid),draft_version_id=cast(:id as uuid),updated_at=now() where id=cast(:page_id as uuid)"),
            {"id": target, "page_id": str(page["id"])},
        )
        await self.session.commit()
        return {"published": True, "surface": self._surface(surface), "version_id": target}

    async def versions(self, surface: str, limit: int = 50) -> list[dict[str, Any]]:
        page = await self._page(surface, create=False)
        if page is None:
            return []
        rows = (
            await self.session.execute(
                text(
                    """
                    select id::text,version_number,label,published,created_at
                    from tenant_public_page_versions
                    where page_id=cast(:page_id as uuid)
                    order by version_number desc
                    limit :limit
                    """
                ),
                {"page_id": str(page["id"]), "limit": max(1, min(limit, 200))},
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    async def set_enabled(self, surface: str, enabled: bool) -> dict[str, Any]:
        page = await self._page(surface)
        assert page is not None
        await self.session.execute(text("update tenant_public_pages set enabled=:enabled,updated_at=now() where id=cast(:id as uuid)"), {"enabled": enabled, "id": str(page["id"])})
        await self.session.commit()
        return {"surface": self._surface(surface), "enabled": enabled}

    async def import_package(self, parsed: ParsedExperience, *, actor: str | None = None) -> dict[str, Any]:
        file_service = TenantFileService(self.context)
        asset_rows: list[dict[str, Any]] = []
        for asset in parsed.assets:
            storage_key = f"experience/{parsed.package_key}/{asset.path}"
            stored = await file_service.upload(storage_key, BytesIO(asset.data), asset.content_type)
            public_url = f"/api/v1/public/assets/{storage_key}"
            await self.session.execute(
                text(
                    """
                    insert into tenant_template_assets(template_key,logical_key,storage_key,public_url,sha256,content_type,size_bytes)
                    values(:template_key,:logical_key,:storage_key,:public_url,:sha256,:content_type,:size_bytes)
                    on conflict(template_key,logical_key) do update
                    set storage_key=excluded.storage_key,public_url=excluded.public_url,sha256=excluded.sha256,
                        content_type=excluded.content_type,size_bytes=excluded.size_bytes,created_at=now()
                    """
                ),
                {
                    "template_key": parsed.package_key,
                    "logical_key": asset.path,
                    "storage_key": storage_key,
                    "public_url": public_url,
                    "sha256": asset.sha256,
                    "content_type": asset.content_type,
                    "size_bytes": int(stored["size_bytes"]),
                },
            )
            asset_rows.append({"path": asset.path, "url": public_url, "sha256": asset.sha256})
        metadata = {"experience_schema": "argws-experience-package/v2", "source_schema": parsed.source_schema, "bindings": deepcopy(parsed.bindings), "package_name": parsed.name}
        landing = await self.save_draft("LANDING", html=parsed.landing_html, template_key=parsed.package_key, theme=parsed.theme, metadata=metadata, label=f"Importação: {parsed.name}", actor=actor)
        booking = await self.save_draft("BOOKING", html=parsed.booking_html, template_key=parsed.package_key, theme=parsed.theme, metadata=metadata, label=f"Importação: {parsed.name}", actor=actor)
        return {"package_key": parsed.package_key, "name": parsed.name, "source_schema": parsed.source_schema, "pages": {"landing": landing, "booking": booking}, "assets": asset_rows, "warnings": list(parsed.warnings)}
