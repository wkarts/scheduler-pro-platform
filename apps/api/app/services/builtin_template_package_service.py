from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

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


def builtin_template_archive(key: str) -> bytes:
    if key not in OFFICIAL_TEMPLATE_KEYS:
        raise KeyError(key)
    path = RESOURCE_DIR / f"{key}.zip"
    if not path.is_file():
        raise RuntimeError(f"Pacote oficial ausente: {key}")
    archive = path.read_bytes()
    report = HtmlTemplatePackageService.validate(archive)
    if not report["valid"]:
        raise RuntimeError(f"Pacote oficial inválido: {key}: {report['errors']}")
    return archive


def builtin_template_package(key: str) -> dict[str, Any]:
    return HtmlTemplatePackageService.ensure(builtin_template_archive(key))


def official_template_families() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in OFFICIAL_TEMPLATE_KEYS:
        parsed = builtin_template_package(key)
        package = parsed["package"]
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
                "surfaces": deepcopy(parsed["surfaces"]),
            }
        )
    return rows


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
                        "ARGWS Visual Builder 2.3.1 — pacote oficial canônico"
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
                        "ARGWS Visual Builder 2.3.1 — pacote oficial canônico"
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
