from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.html_template_import_service import HtmlTemplateImportService
from app.services.html_template_package_service import HtmlTemplatePackageService

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "template-packages"

OFFICIAL_TEMPLATE_KEYS: tuple[str, ...] = (
    "barber-shop-neo-generico",
    "clinica-medica-generico",
    "clinica-odontologica-generico",
    "clinica-veterinaria-generico",
    "martelinho-de-ouro-generico",
    "studio-unhas-generico",
    "tecnologia-generico-simples",
)

LEGACY_SYSTEM_TEMPLATE_KEYS: tuple[str, ...] = (
    "studio-beatriz-nails",
    "agenda-essencial",
    "servicos-profissionais",
    "saude-clinica",
)

def builtin_template_archive(key: str) -> bytes:
    if key not in OFFICIAL_TEMPLATE_KEYS:
        raise KeyError(key)
    folder = RESOURCE_DIR / key
    parts = sorted(folder.glob("part-*.b64"))
    if not parts:
        raise RuntimeError(f"Pacote oficial ausente: {key}")
    encoded = "".join(part.read_text(encoding="utf-8").strip() for part in parts)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise RuntimeError(f"Pacote oficial Base64 inválido: {key}") from exc
    if not payload.startswith(b"PK"):
        raise RuntimeError(f"Pacote oficial ZIP inválido: {key}")
    return payload

async def _remove_legacy_system_templates(session: AsyncSession) -> int:
    result = await session.execute(
        text(
            """
            delete from global_content_templates
            where key = any(cast(:keys as text[]))
              and (
                coalesce(created_by, '') in ('system', 'system:template-bootstrap')
                or coalesce(updated_by, '') in ('system', 'system:template-bootstrap')
              )
            returning id::text
            """
        ),
        {"keys": list(LEGACY_SYSTEM_TEMPLATE_KEYS)},
    )
    removed = len(result.scalars().all())
    await session.commit()
    return removed

async def _existing_surfaces(session: AsyncSession, key: str) -> set[str]:
    rows = (
        await session.execute(
            text("select surface from global_content_templates where key=:key"),
            {"key": key},
        )
    ).scalars().all()
    return {str(value) for value in rows}

async def sync_builtin_template_packages(session: AsyncSession) -> dict[str, Any]:
    removed_legacy = await _remove_legacy_system_templates(session)
    importer = HtmlTemplateImportService(session)
    installed: list[dict[str, Any]] = []

    for key in OFFICIAL_TEMPLATE_KEYS:
        parsed = HtmlTemplatePackageService.ensure(builtin_template_archive(key))
        metadata = parsed["package"]
        documents: dict[str, str] = parsed["documents"]
        if str(metadata["key"]) != key:
            raise RuntimeError(
                f"Chave do pacote oficial divergente: esperado {key}, recebido {metadata['key']}"
            )

        expected = set(documents)
        existing = await _existing_surfaces(session, key)
        missing = expected - existing
        if not missing:
            installed.append({"key": key, "installed": False, "reason": "already-present"})
            continue

        result = await importer.import_pair(
            landing_html=documents.get("LANDING") if "LANDING" in missing else None,
            booking_html=documents.get("BOOKING") if "BOOKING" in missing else None,
            name=str(metadata["name"]),
            description=metadata.get("description"),
            segment=metadata.get("segment"),
            actor="system:template-bootstrap",
            scope="GLOBAL",
            default_for_new_tenants=False,
            publish=True,
            update_existing=False,
        )
        installed.append(
            {
                "key": key,
                "installed": True,
                "surfaces": sorted(missing),
                "result": result,
            }
        )

    return {
        "official_keys": list(OFFICIAL_TEMPLATE_KEYS),
        "removed_legacy": removed_legacy,
        "templates": installed,
    }
