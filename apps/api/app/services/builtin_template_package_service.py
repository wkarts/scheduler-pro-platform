from __future__ import annotations

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


def builtin_template_archive(key: str) -> bytes:
    if key not in OFFICIAL_TEMPLATE_KEYS:
        raise KeyError(key)
    path = RESOURCE_DIR / f"{key}.zip"
    if not path.is_file():
        raise RuntimeError(f"Pacote oficial ausente: {key}")
    archive = path.read_bytes()
    parsed = HtmlTemplatePackageService.ensure(archive)
    if str(parsed["package"]["key"]) != key:
        raise RuntimeError(
            f"Chave do pacote oficial divergente: esperado {key}, recebido {parsed['package']['key']}"
        )
    return archive


async def _existing_surfaces(session: AsyncSession, key: str) -> set[str]:
    rows = (
        await session.execute(
            text("select surface from global_content_templates where key=:key"),
            {"key": key},
        )
    ).scalars().all()
    return {str(value) for value in rows}


async def sync_builtin_template_packages(session: AsyncSession) -> dict[str, Any]:
    """Instala apenas superfícies ausentes das sete famílias oficiais.

    LANDING e BOOKING são páginas independentes. A rotina nunca cria nova
    versão para uma superfície que já existe e jamais aplica modelos em tenants.
    """
    importer = HtmlTemplateImportService(session)
    installed: list[dict[str, Any]] = []

    for key in OFFICIAL_TEMPLATE_KEYS:
        parsed = HtmlTemplatePackageService.ensure(builtin_template_archive(key))
        metadata = parsed["package"]
        documents: dict[str, str] = parsed["documents"]
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
        installed.append({"key": key, "installed": True, "surfaces": sorted(missing), "result": result})

    return {"official_keys": list(OFFICIAL_TEMPLATE_KEYS), "templates": installed, "automatic_tenant_update": False}
