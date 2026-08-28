from __future__ import annotations

import base64
from functools import lru_cache
import hashlib
from io import BytesIO
import json
from pathlib import PurePosixPath, Path
import re
import tarfile
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.html_template_import_service import HtmlTemplateImportService
from app.services.html_template_package_service import HtmlTemplatePackageService

RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "template-catalog" / "v1"
RELEASE_DIR = RESOURCE_DIR / "release-b64"
CATALOG_SCHEMA = "scheduler-pro-official-template-catalog/v1"
EXPECTED_RELEASE_SHA256 = "2c604fa19df53415e66aab1a96641a9227967d8acadc63fea37d06a0d05b8afa"
PART_RE = re.compile(r"^part-(\d{3})\.b64$")
ASSET_PLACEHOLDER_RE = re.compile(r"\{\{ASSET:([0-9a-f]{64}):([a-z0-9.+-]+)\}\}")
MAX_RELEASE_BYTES = 4 * 1024 * 1024
MAX_EXPANDED_BYTES = 8 * 1024 * 1024
MAX_RELEASE_FILES = 128

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


def _safe_release_path(raw: str) -> str | None:
    if not raw or "\\" in raw or raw.startswith("/"):
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return str(path)


@lru_cache(maxsize=1)
def _release_files() -> dict[str, bytes]:
    parts: list[tuple[int, Path]] = []
    for path in RELEASE_DIR.glob("part-*.b64"):
        match = PART_RE.fullmatch(path.name)
        if match:
            parts.append((int(match.group(1)), path))
    parts.sort(key=lambda item: item[0])
    if not parts or [number for number, _ in parts] != list(range(len(parts))):
        raise RuntimeError("Release oficial de templates está ausente ou com partes descontínuas.")

    encoded = "".join(path.read_text(encoding="ascii").strip() for _, path in parts)
    try:
        release = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise RuntimeError("Release oficial de templates possui Base64 inválido.") from exc
    if len(release) > MAX_RELEASE_BYTES:
        raise RuntimeError("Release oficial de templates excede o limite interno.")
    if hashlib.sha256(release).hexdigest() != EXPECTED_RELEASE_SHA256:
        raise RuntimeError("SHA-256 da release oficial de templates diverge do esperado.")

    files: dict[str, bytes] = {}
    total = 0
    try:
        with tarfile.open(fileobj=BytesIO(release), mode="r:gz") as archive:
            members = [member for member in archive.getmembers() if member.isfile()]
            if len(members) > MAX_RELEASE_FILES:
                raise RuntimeError("Release oficial de templates contém arquivos demais.")
            for member in members:
                safe = _safe_release_path(member.name)
                if safe is None or member.issym() or member.islnk():
                    raise RuntimeError(f"Caminho inseguro na release oficial: {member.name}")
                total += int(member.size)
                if total > MAX_EXPANDED_BYTES:
                    raise RuntimeError("Release oficial de templates excede o limite expandido.")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"Não foi possível ler {safe} na release oficial.")
                files[safe] = extracted.read()
    except tarfile.TarError as exc:
        raise RuntimeError("Release oficial de templates está corrompida.") from exc
    return files


def _json_resource(filename: str) -> dict[str, Any]:
    try:
        payload = json.loads(_release_files()[filename].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Recurso oficial ausente ou inválido: {filename}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Recurso oficial inválido: {filename}")
    return payload


def _catalog() -> dict[str, Any]:
    payload = _json_resource("catalog.json")
    if payload.get("schema") != CATALOG_SCHEMA:
        raise RuntimeError("Schema do catálogo oficial de templates inválido.")
    keys = tuple(str(item.get("key") or "") for item in payload.get("templates", []))
    if keys != OFFICIAL_TEMPLATE_KEYS:
        raise RuntimeError("Catálogo oficial diverge das sete famílias esperadas.")
    return payload


def _template_family(key: str) -> dict[str, Any]:
    return _json_resource(f"templates/{key}.json")


def _asset_data_uri(sha256: str, media_type: str) -> str:
    filename = f"assets/{sha256}.b64"
    try:
        encoded = _release_files()[filename].decode("ascii").strip()
        raw = base64.b64decode(encoded, validate=True)
    except (KeyError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(f"Asset oficial inválido: {sha256}") from exc
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise RuntimeError(f"SHA-256 divergente no asset oficial: {sha256}")
    return f"data:image/{media_type};base64,{encoded}"


def _expand_document(source: str, key: str, surface: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return _asset_data_uri(match.group(1), match.group(2))

    expanded = ASSET_PLACEHOLDER_RE.sub(replace, source)
    if "{{ASSET:" in expanded:
        raise RuntimeError(f"Placeholder de asset não resolvido: {key}/{surface}")
    return expanded


def builtin_template_archive(key: str) -> bytes:
    if key not in OFFICIAL_TEMPLATE_KEYS:
        raise KeyError(key)
    _catalog()
    value = _template_family(key)
    manifest = value.get("manifest")
    if not isinstance(manifest, dict) or str(manifest.get("package", {}).get("key") or "") != key:
        raise RuntimeError(f"Manifesto oficial inválido: {key}")
    landing_template = value.get("landing_template")
    booking_template = value.get("booking_template")
    if not isinstance(landing_template, str) or not isinstance(booking_template, str):
        raise RuntimeError(f"Documentos oficiais ausentes: {key}")

    landing = _expand_document(landing_template, key, "landing")
    booking = _expand_document(booking_template, key, "booking")
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED, compresslevel=9) as zipped:
        zipped.writestr("template.json", json.dumps(manifest, ensure_ascii=False))
        zipped.writestr("landing.html", landing)
        zipped.writestr("agendamento.html", booking)
    archive = buffer.getvalue()
    report = HtmlTemplatePackageService.validate(archive)
    if not report["valid"]:
        raise RuntimeError(f"Pacote oficial materializado inválido: {key}: {report['errors']}")
    return archive


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
    """Instala as sete famílias oficiais sem sobrescrever templates existentes."""
    removed_legacy = await _remove_legacy_system_templates(session)
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
        "automatic_tenant_update": False,
    }
