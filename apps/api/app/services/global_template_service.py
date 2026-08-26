from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError

SURFACES = {"LANDING", "BOOKING"}
SCOPES = {"GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"}
STATUSES = {"DRAFT", "PUBLISHED", "INACTIVE"}


class GlobalTemplateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _surface(value: str) -> str:
        surface = value.strip().upper()
        if surface not in SURFACES:
            raise APIError("TEMPLATE_SURFACE_INVALID", "Área de modelo inválida.", 422)
        return surface

    @staticmethod
    def _scope(value: str) -> str:
        scope = value.strip().upper()
        if scope not in SCOPES:
            raise APIError("TEMPLATE_SCOPE_INVALID", "Escopo de modelo inválido.", 422)
        return scope

    @staticmethod
    def _status(value: str) -> str:
        status = value.strip().upper()
        if status not in STATUSES:
            raise APIError("TEMPLATE_STATUS_INVALID", "Status de modelo inválido.", 422)
        return status

    async def list(
        self,
        *,
        surface: str | None = None,
        tenant_id: str | None = None,
        include_internal: bool = False,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: dict[str, Any] = {}
        if surface:
            clauses.append("t.surface=:surface")
            params["surface"] = self._surface(surface)
        if tenant_id:
            clauses.append(
                """
                (
                  t.scope='GLOBAL'
                  or (t.scope='SELECTED' and t.selected_tenant_ids ? :tenant_id)
                  or (t.scope='EXCLUSIVE' and t.exclusive_tenant_id=cast(:tenant_id as uuid))
                )
                """
            )
            clauses.append("t.status='PUBLISHED'")
            params["tenant_id"] = tenant_id
        elif not include_internal:
            clauses.append("t.scope<>'INTERNAL'")
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select t.id::text, t.surface, t.key, t.name, t.description,
                           t.segment, t.status, t.scope, t.default_for_new_tenants,
                           t.exclusive_tenant_id::text, t.selected_tenant_ids,
                           t.latest_version, t.created_at, t.updated_at,
                           (
                             select max(v.version_number)
                             from global_content_template_versions v
                             where v.template_id=t.id and v.published=true
                           ) as published_version
                    from global_content_templates t
                    where {' and '.join(clauses)}
                    order by t.surface, t.name, t.key
                    """
                ),
                params,
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    async def get(self, template_id: str) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    select id::text, surface, key, name, description, segment,
                           status, scope, default_for_new_tenants,
                           exclusive_tenant_id::text, selected_tenant_ids,
                           latest_version, created_by, updated_by,
                           created_at, updated_at
                    from global_content_templates
                    where id=cast(:id as uuid)
                    limit 1
                    """
                ),
                {"id": template_id},
            )
        ).mappings().first()
        if row is None:
            raise APIError("GLOBAL_TEMPLATE_NOT_FOUND", "Modelo global não encontrado.", 404)
        versions = (
            await self.session.execute(
                text(
                    """
                    select id::text, version_number, changelog, published,
                           created_by, created_at
                    from global_content_template_versions
                    where template_id=cast(:id as uuid)
                    order by version_number desc
                    """
                ),
                {"id": template_id},
            )
        ).mappings().all()
        return {**dict(row), "versions": [dict(item) for item in versions]}

    async def create(
        self,
        payload: dict[str, Any],
        *,
        actor: str | None,
    ) -> dict[str, Any]:
        surface = self._surface(str(payload.get("surface") or ""))
        scope = self._scope(str(payload.get("scope") or "INTERNAL"))
        status = self._status(str(payload.get("status") or "DRAFT"))
        key = str(payload.get("key") or "").strip().lower()
        if not key or len(key) > 120 or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in key):
            raise APIError("GLOBAL_TEMPLATE_KEY_INVALID", "Use uma chave com letras minúsculas, números e hífen.", 422)
        name = str(payload.get("name") or "").strip()
        if len(name) < 2 or len(name) > 180:
            raise APIError("GLOBAL_TEMPLATE_NAME_INVALID", "Nome do modelo inválido.", 422)
        selected = [str(item) for item in payload.get("selected_tenant_ids") or []]
        exclusive = str(payload.get("exclusive_tenant_id") or "").strip() or None
        if scope == "EXCLUSIVE" and not exclusive:
            raise APIError("GLOBAL_TEMPLATE_TENANT_REQUIRED", "Escolha o tenant exclusivo.", 422)
        template_id = await self.session.scalar(
            text(
                """
                insert into global_content_templates(
                  surface,key,name,description,segment,status,scope,
                  default_for_new_tenants,exclusive_tenant_id,selected_tenant_ids,
                  latest_version,created_by,updated_by
                ) values(
                  :surface,:key,:name,:description,:segment,:status,:scope,
                  :default_for_new_tenants,cast(:exclusive_tenant_id as uuid),
                  cast(:selected_tenant_ids as jsonb),0,:actor,:actor
                )
                returning id::text
                """
            ),
            {
                "surface": surface,
                "key": key,
                "name": name,
                "description": str(payload.get("description") or "").strip() or None,
                "segment": str(payload.get("segment") or "").strip() or None,
                "status": status,
                "scope": scope,
                "default_for_new_tenants": bool(payload.get("default_for_new_tenants", False)),
                "exclusive_tenant_id": exclusive,
                "selected_tenant_ids": __import__("json").dumps(selected),
                "actor": actor,
            },
        )
        content = payload.get("content")
        if isinstance(content, dict):
            await self.create_version(
                str(template_id),
                content,
                changelog=str(payload.get("changelog") or "Versão inicial"),
                actor=actor,
                publish=status == "PUBLISHED",
            )
        else:
            await self.session.commit()
        return await self.get(str(template_id))

    async def update_metadata(
        self,
        template_id: str,
        payload: dict[str, Any],
        *,
        actor: str | None,
    ) -> dict[str, Any]:
        current = await self.get(template_id)
        scope = self._scope(str(payload.get("scope", current["scope"])))
        status = self._status(str(payload.get("status", current["status"])))
        selected = payload.get("selected_tenant_ids", current.get("selected_tenant_ids") or [])
        exclusive = payload.get("exclusive_tenant_id", current.get("exclusive_tenant_id"))
        if scope == "EXCLUSIVE" and not exclusive:
            raise APIError("GLOBAL_TEMPLATE_TENANT_REQUIRED", "Escolha o tenant exclusivo.", 422)
        await self.session.execute(
            text(
                """
                update global_content_templates
                set name=:name, description=:description, segment=:segment,
                    status=:status, scope=:scope,
                    default_for_new_tenants=:default_for_new_tenants,
                    exclusive_tenant_id=cast(:exclusive_tenant_id as uuid),
                    selected_tenant_ids=cast(:selected_tenant_ids as jsonb),
                    updated_by=:actor, updated_at=now()
                where id=cast(:id as uuid)
                """
            ),
            {
                "id": template_id,
                "name": str(payload.get("name", current["name"])).strip(),
                "description": str(payload.get("description", current.get("description") or "")).strip() or None,
                "segment": str(payload.get("segment", current.get("segment") or "")).strip() or None,
                "status": status,
                "scope": scope,
                "default_for_new_tenants": bool(payload.get("default_for_new_tenants", current["default_for_new_tenants"])),
                "exclusive_tenant_id": str(exclusive).strip() if exclusive else None,
                "selected_tenant_ids": __import__("json").dumps([str(item) for item in selected]),
                "actor": actor,
            },
        )
        await self.session.commit()
        return await self.get(template_id)

    async def create_version(
        self,
        template_id: str,
        content: dict[str, Any],
        *,
        changelog: str | None,
        actor: str | None,
        publish: bool = False,
    ) -> dict[str, Any]:
        await self.get(template_id)
        await self.session.execute(
            text("select pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"scheduler-pro:global-template:{template_id}"},
        )
        next_version = int(
            await self.session.scalar(
                text(
                    "select coalesce(max(version_number),0)+1 from global_content_template_versions where template_id=cast(:id as uuid)"
                ),
                {"id": template_id},
            )
            or 1
        )
        version_id = await self.session.scalar(
            text(
                """
                insert into global_content_template_versions(
                  template_id,version_number,content,changelog,published,created_by
                ) values(
                  cast(:id as uuid),:version,cast(:content as jsonb),:changelog,false,:actor
                ) returning id::text
                """
            ),
            {
                "id": template_id,
                "version": next_version,
                "content": __import__("json").dumps(content, ensure_ascii=False),
                "changelog": changelog,
                "actor": actor,
            },
        )
        await self.session.execute(
            text(
                "update global_content_templates set latest_version=:version,updated_by=:actor,updated_at=now() where id=cast(:id as uuid)"
            ),
            {"id": template_id, "version": next_version, "actor": actor},
        )
        await self.session.commit()
        if publish:
            await self.publish_version(template_id, next_version, actor=actor)
        return {"id": str(version_id), "template_id": template_id, "version_number": next_version, "published": publish}

    async def publish_version(
        self,
        template_id: str,
        version_number: int,
        *,
        actor: str | None,
    ) -> dict[str, Any]:
        exists = await self.session.scalar(
            text(
                "select exists(select 1 from global_content_template_versions where template_id=cast(:id as uuid) and version_number=:version)"
            ),
            {"id": template_id, "version": version_number},
        )
        if not exists:
            raise APIError("GLOBAL_TEMPLATE_VERSION_NOT_FOUND", "Versão do modelo não encontrada.", 404)
        await self.session.execute(
            text("update global_content_template_versions set published=false where template_id=cast(:id as uuid)"),
            {"id": template_id},
        )
        await self.session.execute(
            text(
                "update global_content_template_versions set published=true where template_id=cast(:id as uuid) and version_number=:version"
            ),
            {"id": template_id, "version": version_number},
        )
        await self.session.execute(
            text(
                """
                update global_content_templates
                set status='PUBLISHED',latest_version=greatest(latest_version,:version),updated_by=:actor,updated_at=now()
                where id=cast(:id as uuid)
                """
            ),
            {"id": template_id, "version": version_number, "actor": actor},
        )
        await self.session.commit()
        return await self.get(template_id)

    async def content(
        self,
        *,
        template_id: str | None = None,
        surface: str | None = None,
        key: str | None = None,
        version_number: int | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        where: list[str] = []
        if template_id:
            where.append("t.id=cast(:template_id as uuid)")
            params["template_id"] = template_id
        else:
            if not surface or not key:
                raise APIError("GLOBAL_TEMPLATE_REFERENCE_REQUIRED", "Informe o modelo global.", 422)
            where.extend(["t.surface=:surface", "t.key=:key"])
            params.update({"surface": self._surface(surface), "key": key})
        if tenant_id:
            where.append("t.status='PUBLISHED'")
            where.append(
                "(t.scope='GLOBAL' or (t.scope='SELECTED' and t.selected_tenant_ids ? :tenant_id) or (t.scope='EXCLUSIVE' and t.exclusive_tenant_id=cast(:tenant_id as uuid)))"
            )
            params["tenant_id"] = tenant_id
        row = (
            await self.session.execute(
                text(
                    f"select t.id::text,t.surface,t.key,t.name,t.scope,t.status from global_content_templates t where {' and '.join(where)} limit 1"
                ),
                params,
            )
        ).mappings().first()
        if row is None:
            raise APIError("GLOBAL_TEMPLATE_NOT_FOUND", "Modelo global não encontrado ou indisponível para este tenant.", 404)
        version_params: dict[str, Any] = {"id": str(row["id"])}
        version_where = "template_id=cast(:id as uuid)"
        if version_number is not None:
            version_where += " and version_number=:version"
            version_params["version"] = version_number
        else:
            version_where += " and published=true"
        version = (
            await self.session.execute(
                text(
                    f"select id::text,version_number,content,published,created_at from global_content_template_versions where {version_where} order by version_number desc limit 1"
                ),
                version_params,
            )
        ).mappings().first()
        if version is None:
            raise APIError("GLOBAL_TEMPLATE_VERSION_NOT_FOUND", "O modelo ainda não possui uma versão publicada.", 404)
        return {**dict(row), "version": {**dict(version), "content": deepcopy(version["content"])}}

    async def duplicate(
        self,
        template_id: str,
        *,
        new_key: str,
        new_name: str,
        actor: str | None,
    ) -> dict[str, Any]:
        source = await self.get(template_id)
        content = await self.content(template_id=template_id, version_number=int(source["latest_version"] or 1))
        return await self.create(
            {
                "surface": source["surface"],
                "key": new_key,
                "name": new_name,
                "description": source.get("description"),
                "segment": source.get("segment"),
                "status": "DRAFT",
                "scope": "INTERNAL",
                "content": content["version"]["content"],
                "changelog": f"Duplicado de {source['key']}",
            },
            actor=actor,
        )
