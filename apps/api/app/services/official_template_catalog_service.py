from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.html_template_import_service import HtmlTemplateImportService
from app.services.html_template_package_service import HtmlTemplatePackageService

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "template-packages"
CATALOG_MARKER_KEY = "scheduler_pro_official_template_catalog"
CATALOG_REVISION = "html-package-v2-20260827"

# Pacotes oficiais entregues para o Scheduler Pro em 2026-08-27. Os arquivos
# ficam codificados em partes de texto para permanecerem byte-perfect no Git e
# serem reconstruídos/validados antes de qualquer alteração do catálogo.
OFFICIAL_TEMPLATE_PACKAGES: tuple[tuple[str, str], ...] = (
    (
        "barber-shop-neo-generico",
        "1b72af9345c7c883e449f42b2093ef9e4f97bdb52e276cc41c841079bfa196be",
    ),
    (
        "clinica-medica-generico",
        "8f24e489740a37a7e548265a150518f0ef4db9bc3a4a9791a4ad88ec9f584415",
    ),
    (
        "clinica-odontologica-generico",
        "022325584eefe7e7c3a578df8b9e3ce23e494212a4f0d2a6897a87804620ffef",
    ),
    (
        "clinica-veterinaria-generico",
        "92afabbdbe74f72d8422e633c68398f60a8becf6445df2ffe5df76c1761f55cf",
    ),
    (
        "martelinho-de-ouro-generico",
        "5531359f8c111dc6fe7f96db18cc11b31bba9c1ad9cce2903de32f341786e3e6",
    ),
    (
        "studio-unhas-generico",
        "ef84798ef93aa50abc33b769eae027c9f6a7f68c8a1b9697334ee3d424723ae2",
    ),
    (
        "tecnologia-generico-simples",
        "c0fc25051cefb6f58c762dee301281e0653d88611a0e14ebd646b5b7fe0cdd20",
    ),
)
OFFICIAL_TEMPLATE_KEYS = tuple(item[0] for item in OFFICIAL_TEMPLATE_PACKAGES)


def package_bytes(key: str, expected_sha256: str) -> bytes:
    package_dir = RESOURCE_DIR / key
    parts = sorted(package_dir.glob("part-*.b64"))
    if not parts:
        raise RuntimeError(f"Pacote oficial ausente: {key}")
    encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise RuntimeError(f"Pacote oficial Base64 inválido: {key}") from exc
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError(
            f"Pacote oficial corrompido: {key}; sha256={digest}, esperado={expected_sha256}"
        )
    return payload


async def _catalog_revision(session: AsyncSession) -> str | None:
    row = (
        await session.execute(
            text("select rules from feature_flags where key=:key limit 1"),
            {"key": CATALOG_MARKER_KEY},
        )
    ).mappings().first()
    if row is None or not isinstance(row["rules"], dict):
        return None
    return str(row["rules"].get("revision") or "") or None


async def _set_catalog_revision(session: AsyncSession) -> None:
    rules = json.dumps(
        {
            "revision": CATALOG_REVISION,
            "keys": list(OFFICIAL_TEMPLATE_KEYS),
            "source": "official-template-packages",
        }
    )
    await session.execute(
        text(
            """
            insert into feature_flags(key, enabled, rules)
            values(:key, true, cast(:rules as jsonb))
            on conflict(key) do update set enabled=true, rules=excluded.rules
            """
        ),
        {"key": CATALOG_MARKER_KEY, "rules": rules},
    )
    await session.commit()


async def _existing_surfaces(session: AsyncSession, key: str) -> set[str]:
    values = (
        await session.execute(
            text("select surface from global_content_templates where key=:key"),
            {"key": key},
        )
    ).scalars().all()
    return {str(value) for value in values}


async def _install_package(
    session: AsyncSession,
    *,
    key: str,
    expected_sha256: str,
    only_missing: bool,
) -> dict[str, Any]:
    parsed = HtmlTemplatePackageService.ensure(package_bytes(key, expected_sha256))
    metadata = parsed["package"]
    documents: dict[str, str] = parsed["documents"]
    declared_key = str(metadata["key"])
    if declared_key != key:
        raise RuntimeError(
            f"Pacote oficial com chave divergente: arquivo={key}, manifesto={declared_key}"
        )

    existing = await _existing_surfaces(session, key) if only_missing else set()
    landing = documents.get("LANDING") if "LANDING" not in existing else None
    booking = documents.get("BOOKING") if "BOOKING" not in existing else None
    if not landing and not booking:
        return {"key": key, "installed": False, "reason": "already-present"}

    result = await HtmlTemplateImportService(session).import_pair(
        landing_html=landing,
        booking_html=booking,
        name=str(metadata["name"]),
        description=metadata.get("description"),
        segment=metadata.get("segment"),
        actor="system:official-template-catalog",
        scope="GLOBAL",
        default_for_new_tenants=False,
        publish=True,
        update_existing=False,
    )
    return {
        "key": key,
        "installed": True,
        "surfaces": sorted(
            surface
            for surface, document in (("LANDING", landing), ("BOOKING", booking))
            if document
        ),
        "result": result,
    }


async def replace_official_template_catalog(session: AsyncSession) -> dict[str, Any]:
    """Substitui uma única vez o catálogo antigo pelos sete pacotes oficiais.

    O catálogo global pode ser removido porque a aplicação do modelo ao tenant
    copia/versiona o conteúdo no banco isolado do cliente. Landing Pages e
    Páginas de Agendamento já publicadas pelos tenants não são apagadas nem
    alteradas por esta operação.

    Após a revisão ser marcada, novos boots apenas reparam pacotes/superfícies
    ausentes; não sobrescrevem versões que o Control Plane tenha personalizado.
    """

    revision = await _catalog_revision(session)
    replacing = revision != CATALOG_REVISION
    if replacing:
        await session.execute(text("delete from global_content_template_versions"))
        await session.execute(text("delete from global_content_templates"))
        await session.commit()

    installed: list[dict[str, Any]] = []
    for key, digest in OFFICIAL_TEMPLATE_PACKAGES:
        installed.append(
            await _install_package(
                session,
                key=key,
                expected_sha256=digest,
                only_missing=not replacing,
            )
        )

    if replacing:
        await _set_catalog_revision(session)

    return {
        "revision": CATALOG_REVISION,
        "replaced": replacing,
        "official_keys": list(OFFICIAL_TEMPLATE_KEYS),
        "templates": installed,
        "tenant_pages_changed": False,
    }
