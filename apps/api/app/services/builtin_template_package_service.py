from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from io import BytesIO
import json
from pathlib import Path
from typing import Any, cast
from zipfile import ZipFile

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.global_template_service import GlobalTemplateService
from app.services.html_template_contract import HtmlTemplateContract
from app.services.html_template_package_service import HtmlTemplatePackageService

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "template-packages"
DEFAULT_TEMPLATE_KEY = "scheduler-pro-padrao-generico"
OFFICIAL_TEMPLATE_KEYS: tuple[str, ...] = (
    DEFAULT_TEMPLATE_KEY,
    "barber-shop-neo-generico",
    "clinica-medica-generico",
    "clinica-odontologica-generico",
    "clinica-veterinaria-generico",
    "martelinho-de-ouro-generico",
    "studio-unhas-generico",
    "tecnologia-generico-simples",
)
SURFACE_SUFFIX = {
    "LANDING": "",
    "BOOKING": " — Agendamento",
    "LOGIN": " — Login",
}


@lru_cache(maxsize=len(OFFICIAL_TEMPLATE_KEYS))
def builtin_template_archive(key: str) -> bytes:
    if key not in OFFICIAL_TEMPLATE_KEYS:
        raise KeyError(key)
    path = RESOURCE_DIR / f"{key}.zip"
    if not path.is_file():
        raise RuntimeError(f"Pacote oficial ausente: {key}")
    return path.read_bytes()


@lru_cache(maxsize=len(OFFICIAL_TEMPLATE_KEYS))
def builtin_template_package(key: str) -> dict[str, Any]:
    return HtmlTemplatePackageService.ensure(builtin_template_archive(key))


@lru_cache(maxsize=len(OFFICIAL_TEMPLATE_KEYS))
def _builtin_manifest(key: str) -> dict[str, Any]:
    """Lê somente template.json para o catálogo leve.

    O Workspace não precisa descompactar/validar HTMLs de vários megabytes apenas
    para desenhar os cards. A validação completa continua em
    ``builtin_template_package`` no bootstrap e no uso da superfície.
    """
    try:
        with ZipFile(BytesIO(builtin_template_archive(key))) as archive:
            raw = archive.read("template.json")
        decoded: object = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Manifesto oficial inválido: {key}") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"Manifesto oficial deve ser um objeto JSON: {key}")
    manifest = cast(dict[str, Any], decoded)
    if manifest.get("schema") != "scheduler-pro-template-package/v1":
        raise RuntimeError(f"Schema oficial inválido: {key}")
    package = manifest.get("package") or {}
    if package.get("key") != key:
        raise RuntimeError(f"Chave do manifesto oficial diverge: {key}")
    return manifest


@lru_cache(maxsize=1)
def _official_template_families_cached() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for key in OFFICIAL_TEMPLATE_KEYS:
        package = (_builtin_manifest(key).get("package") or {})
        rows.append(
            {
                "key": key,
                "name": package["name"],
                "description": package.get("description"),
                "segment": package.get("segment"),
                "platform_default": key == DEFAULT_TEMPLATE_KEY,
                "default_for_new_tenants": bool(
                    package.get("default_for_new_tenants")
                )
                or key == DEFAULT_TEMPLATE_KEY,
                "surfaces": deepcopy(package.get("surfaces") or {}),
            }
        )
    return tuple(rows)


def official_template_families() -> list[dict[str, Any]]:
    # Retorna cópia para impedir que serialização/consumidores alterem o cache canônico.
    return deepcopy(list(_official_template_families_cached()))


async def _template_id(
    session: AsyncSession,
    surface: str,
    key: str,
) -> str | None:
    value = await session.scalar(
        text(
            "select id::text from global_content_templates "
            "where surface=:surface and key=:key limit 1"
        ),
        {"surface": surface, "key": key},
    )
    return str(value) if value else None


async def _published_content(
    session: AsyncSession,
    template_id: str,
) -> dict[str, Any] | None:
    value = await session.scalar(
        text(
            "select content from global_content_template_versions "
            "where template_id=cast(:id as uuid) and published=true "
            "order by version_number desc limit 1"
        ),
        {"id": template_id},
    )
    return deepcopy(value) if isinstance(value, dict) else None


async def sync_builtin_template_packages(session: AsyncSession) -> dict[str, Any]:
    """Sincroniza a biblioteca oficial sem aplicar páginas nos tenants.

    Páginas já personalizadas/publicadas permanecem intactas. O template genérico
    é apenas fallback e padrão para novas configurações sem personalização.
    """
    service = GlobalTemplateService(session)
    results: list[dict[str, Any]] = []

    for key in OFFICIAL_TEMPLATE_KEYS:
        parsed = builtin_template_package(key)
        metadata = parsed["package"]
        source_scope = str(metadata.get("scope") or "INTERNAL").upper()
        storage_scope = "GLOBAL" if source_scope == "PLATFORM_DEFAULT" else source_scope
        default_for_new_tenants = (
            bool(metadata.get("default_for_new_tenants"))
            or key == DEFAULT_TEMPLATE_KEY
        )

        for surface, html_document in parsed["documents"].items():
            content = HtmlTemplateContract.wrapper(
                html_document,
                expected_surface=surface,
            )
            common = {
                "name": f"{metadata['name']}{SURFACE_SUFFIX.get(surface, '')}",
                "description": metadata.get("description"),
                "segment": metadata.get("segment"),
                "scope": storage_scope,
                "default_for_new_tenants": default_for_new_tenants,
                "exclusive_tenant_id": None,
                "selected_tenant_ids": [],
                "status": "PUBLISHED",
            }
            existing = await _template_id(session, surface, key)
            if existing:
                current = await _published_content(session, existing)
                await service.update_metadata(
                    existing,
                    common,
                    actor="system:template-bootstrap",
                )
                if current == content:
                    results.append(
                        {"key": key, "surface": surface, "updated": False}
                    )
                    continue
                version = await service.create_version(
                    existing,
                    content,
                    changelog=(
                        "ARGWS Visual Builder 2.4.0 — pacote oficial canônico"
                    ),
                    actor="system:template-bootstrap",
                    publish=True,
                )
                results.append(
                    {
                        "key": key,
                        "surface": surface,
                        "updated": True,
                        "version": int(version["version_number"]),
                    }
                )
                continue

            created = await service.create(
                {
                    "surface": surface,
                    "key": key,
                    **common,
                    "content": content,
                    "changelog": (
                        "ARGWS Visual Builder 2.4.0 — pacote oficial canônico"
                    ),
                },
                actor="system:template-bootstrap",
            )
            await service.publish_version(
                str(created["id"]),
                int(created.get("latest_version") or 1),
                actor="system:template-bootstrap",
            )
            results.append(
                {
                    "key": key,
                    "surface": surface,
                    "updated": True,
                    "created": True,
                }
            )

    return {
        "default_template_key": DEFAULT_TEMPLATE_KEY,
        "official_keys": list(OFFICIAL_TEMPLATE_KEYS),
        "surfaces": ["LANDING", "BOOKING", "LOGIN"],
        "templates": results,
        "automatic_tenant_update": False,
    }
