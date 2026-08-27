from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.html_template_import_service import HtmlTemplateImportService
from app.services.html_template_package_service import HtmlTemplatePackageService

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "template-packages"

BUILTIN_TEMPLATE_PACKAGES: tuple[str, ...] = (
    "barber-shop-neo-generico.zip",
    "clinica-medica-generico.zip",
    "clinica-odontologica-generico.zip",
    "clinica-veterinaria-generico.zip",
    "martelinho-de-ouro-generico.zip",
    "studio-unhas-generico.zip",
    "tecnologia-generico-simples.zip",
)


async def _existing_surfaces(session: AsyncSession, key: str) -> set[str]:
    rows = (
        await session.execute(
            text("select surface from global_content_templates where key=:key"),
            {"key": key},
        )
    ).scalars().all()
    return {str(value) for value in rows}


async def sync_builtin_template_packages(session: AsyncSession) -> list[dict[str, Any]]:
    """Instala uma vez os pacotes HTML oficiais enviados para esta release.

    Depois da primeira instalação, o Control Plane passa a ser a autoridade de
    escopo, publicação e versionamento. Deploys futuros não sobrescrevem uma
    família que já exista, nem mesmo quando ela tiver sido personalizada pelo
    administrador.
    """

    results: list[dict[str, Any]] = []
    importer = HtmlTemplateImportService(session)
    for filename in BUILTIN_TEMPLATE_PACKAGES:
        path = RESOURCE_DIR / filename
        if not path.is_file():
            raise RuntimeError(f"Pacote oficial ausente: {path}")
        parsed = HtmlTemplatePackageService.ensure(path.read_bytes())
        metadata = parsed["package"]
        documents: dict[str, str] = parsed["documents"]
        key = str(metadata["key"])
        expected = set(documents)
        existing = await _existing_surfaces(session, key)
        missing = expected - existing
        if not missing:
            results.append(
                {"key": key, "installed": False, "reason": "already-present"}
            )
            continue

        imported = await importer.import_pair(
            landing_html=documents.get("LANDING") if "LANDING" in missing else None,
            booking_html=documents.get("BOOKING") if "BOOKING" in missing else None,
            name=str(metadata["name"]),
            description=metadata.get("description"),
            segment=metadata.get("segment"),
            actor="system:template-bootstrap",
            scope="INTERNAL",
            default_for_new_tenants=False,
            publish=True,
            update_existing=False,
        )
        results.append(
            {
                "key": key,
                "installed": True,
                "surfaces": sorted(missing),
                "result": imported,
            }
        )
    return results
