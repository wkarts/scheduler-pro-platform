from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError

POLICY_FLAG_KEY = "argws_visual_builder_release_policy"
TENANT_POLICY_KEY = "argws_visual_builder"
TENANT_SELECTION_KEY = "visual_builder_version"
DEFAULT_VERSION = "2.0.1"
SUPPORTED_VERSIONS = ("1.0.0", "2.0.0", "2.0.1")
RELEASES: tuple[dict[str, Any], ...] = (
    {
        "version": "1.0.0",
        "label": "ARGWS Visual Builder 1.0.0",
        "schema": "argws-visual-builder/v2",
        "channel": "legacy-test",
        "recommended": False,
        "description": "Release estável anterior, preservada para testes e compatibilidade.",
    },
    {
        "version": "2.0.0",
        "label": "ARGWS Visual Builder 2.0.0",
        "schema": "argws-visual-builder/v3",
        "channel": "stable",
        "recommended": False,
        "description": "Release 2.0 original do editor universal v3.",
    },
    {
        "version": "2.0.1",
        "label": "ARGWS Visual Builder 2.0.1",
        "schema": "argws-visual-builder/v3",
        "channel": "current",
        "recommended": True,
        "description": "Release New-Only atual e recomendada para novas páginas.",
    },
)


def _version(value: Any, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    candidate = str(value or "").strip()
    if candidate not in SUPPORTED_VERSIONS:
        raise APIError(
            "VISUAL_BUILDER_VERSION_UNSUPPORTED",
            "Versão do ARGWS Visual Builder não suportada.",
            422,
            {
                "version": candidate,
                "supported_versions": list(SUPPORTED_VERSIONS),
            },
        )
    return candidate


def _ordered_versions(values: list[str] | tuple[str, ...]) -> list[str]:
    requested = {str(item).strip() for item in values}
    invalid = sorted(
        item for item in requested if item and item not in SUPPORTED_VERSIONS
    )
    if invalid:
        raise APIError(
            "VISUAL_BUILDER_VERSION_UNSUPPORTED",
            "Uma ou mais versões do ARGWS Visual Builder não são suportadas.",
            422,
            {
                "versions": invalid,
                "supported_versions": list(SUPPORTED_VERSIONS),
            },
        )
    return [version for version in SUPPORTED_VERSIONS if version in requested]


class VisualBuilderVersionService:
    def __init__(self, platform_session: AsyncSession) -> None:
        self.platform_session = platform_session

    async def _tenant_exists(self, tenant_id: str) -> bool:
        return bool(
            await self.platform_session.scalar(
                text(
                    "select exists(select 1 from tenants "
                    "where id=cast(:tenant_id as uuid))"
                ),
                {"tenant_id": tenant_id},
            )
        )

    async def platform_policy(self) -> dict[str, Any]:
        row = (
            await self.platform_session.execute(
                text(
                    "select enabled, rules from feature_flags "
                    "where key=:key limit 1"
                ),
                {"key": POLICY_FLAG_KEY},
            )
        ).mappings().first()
        rules = dict(row["rules"] or {}) if row else {}
        configured = str(rules.get("default_version") or "").strip()
        default = configured if configured in SUPPORTED_VERSIONS else DEFAULT_VERSION
        return {
            "product": "ARGWS Visual Builder Editor",
            "default_version": default,
            "supported_versions": list(SUPPORTED_VERSIONS),
            "releases": [dict(item) for item in RELEASES],
            "policy_configured": bool(row),
        }

    async def set_platform_default(self, version: str) -> dict[str, Any]:
        normalized = _version(version)
        await self.platform_session.execute(
            text(
                """
                insert into feature_flags(key, enabled, rules)
                values(:key, true, cast(:rules as jsonb))
                on conflict(key) do update set enabled=true, rules=excluded.rules
                """
            ),
            {
                "key": POLICY_FLAG_KEY,
                "rules": json.dumps({"default_version": normalized}),
            },
        )
        await self.platform_session.commit()
        return await self.platform_policy()

    async def tenant_policy(self, tenant_id: str) -> dict[str, Any]:
        row = (
            await self.platform_session.execute(
                text(
                    "select id::text, coalesce(settings, '{}'::jsonb) as settings "
                    "from tenants where id=cast(:tenant_id as uuid) limit 1"
                ),
                {"tenant_id": tenant_id},
            )
        ).mappings().first()
        if row is None:
            raise APIError("TENANT_NOT_FOUND", "Empresa não encontrada.", 404)
        platform = await self.platform_policy()
        tenant_settings = dict(row["settings"] or {})
        raw = tenant_settings.get(TENANT_POLICY_KEY)
        if isinstance(raw, dict):
            explicit = True
            policy: dict[str, Any] = {str(key): value for key, value in raw.items()}
        else:
            explicit = False
            policy = {}
        if explicit:
            allowed = _ordered_versions(list(policy.get("allowed_versions") or []))
            configured_default = str(policy.get("default_version") or "").strip()
            tenant_default = configured_default if configured_default in allowed else None
        else:
            allowed = [str(platform["default_version"])]
            tenant_default = str(platform["default_version"])
        return {
            "tenant_id": tenant_id,
            "explicit": explicit,
            "allowed_versions": allowed,
            "default_version": tenant_default,
            "platform_default_version": platform["default_version"],
            "supported_versions": list(SUPPORTED_VERSIONS),
            "releases": [
                {**dict(item), "allowed": item["version"] in allowed}
                for item in RELEASES
            ],
        }

    async def set_tenant_policy(
        self,
        tenant_id: str,
        *,
        allowed_versions: list[str],
        default_version: str | None,
    ) -> dict[str, Any]:
        allowed = _ordered_versions(allowed_versions)
        tenant_default = _version(default_version, allow_none=True)
        if tenant_default and tenant_default not in allowed:
            raise APIError(
                "VISUAL_BUILDER_DEFAULT_NOT_ALLOWED",
                "A versão padrão do cliente precisa estar entre as versões liberadas.",
                422,
                {
                    "default_version": tenant_default,
                    "allowed_versions": allowed,
                },
            )
        if not await self._tenant_exists(tenant_id):
            raise APIError("TENANT_NOT_FOUND", "Empresa não encontrada.", 404)
        payload = {
            "allowed_versions": allowed,
            "default_version": tenant_default,
        }
        await self.platform_session.execute(
            text(
                """
                update tenants
                set settings=jsonb_set(
                    coalesce(settings, '{}'::jsonb),
                    '{argws_visual_builder}',
                    cast(:policy as jsonb),
                    true
                )
                where id=cast(:tenant_id as uuid)
                """
            ),
            {
                "tenant_id": tenant_id,
                "policy": json.dumps(payload),
            },
        )
        await self.platform_session.commit()
        return await self.tenant_policy(tenant_id)

    async def reset_tenant_policy(self, tenant_id: str) -> dict[str, Any]:
        if not await self._tenant_exists(tenant_id):
            raise APIError("TENANT_NOT_FOUND", "Empresa não encontrada.", 404)
        await self.platform_session.execute(
            text(
                """
                update tenants
                set settings=coalesce(settings, '{}'::jsonb) - 'argws_visual_builder'
                where id=cast(:tenant_id as uuid)
                """
            ),
            {"tenant_id": tenant_id},
        )
        await self.platform_session.commit()
        return await self.tenant_policy(tenant_id)

    async def tenant_state(
        self,
        tenant_id: str,
        tenant_session: AsyncSession,
    ) -> dict[str, Any]:
        policy = await self.tenant_policy(tenant_id)
        selected = await tenant_session.scalar(
            text("select value from tenant_settings where key=:key limit 1"),
            {"key": TENANT_SELECTION_KEY},
        )
        selected_version = str(selected or "").strip()
        if selected_version not in SUPPORTED_VERSIONS:
            selected_version = ""
        allowed = list(policy["allowed_versions"])
        effective = ""
        for candidate in (
            selected_version,
            str(policy.get("default_version") or ""),
            str(policy.get("platform_default_version") or ""),
            *reversed(allowed),
        ):
            if candidate and candidate in allowed:
                effective = candidate
                break
        return {
            **policy,
            "selected_version": selected_version or None,
            "effective_version": effective or None,
            "available": bool(allowed and effective),
        }

    async def select_tenant_version(
        self,
        tenant_id: str,
        tenant_session: AsyncSession,
        version: str | None,
    ) -> dict[str, Any]:
        policy = await self.tenant_policy(tenant_id)
        if version is None or not str(version).strip():
            await tenant_session.execute(
                text("delete from tenant_settings where key=:key"),
                {"key": TENANT_SELECTION_KEY},
            )
            await tenant_session.commit()
            return await self.tenant_state(tenant_id, tenant_session)
        normalized = _version(version)
        if normalized not in policy["allowed_versions"]:
            raise APIError(
                "VISUAL_BUILDER_VERSION_NOT_RELEASED",
                "Esta versão do ARGWS Visual Builder não foi liberada para a empresa.",
                403,
                {
                    "version": normalized,
                    "allowed_versions": policy["allowed_versions"],
                },
            )
        await tenant_session.execute(
            text(
                """
                insert into tenant_settings(key, value, updated_at)
                values(:key, cast(:value as jsonb), now())
                on conflict(key) do update set value=excluded.value, updated_at=now()
                """
            ),
            {
                "key": TENANT_SELECTION_KEY,
                "value": json.dumps(normalized),
            },
        )
        await tenant_session.commit()
        return await self.tenant_state(tenant_id, tenant_session)
