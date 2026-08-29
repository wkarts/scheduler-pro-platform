from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, cast
from zipfile import BadZipFile, ZipFile

from app.core.errors import APIError

EXPERIENCE_SCHEMA = "argws-experience-package/v2"
LEGACY_SCHEMA = "scheduler-pro-template-package/v1"
MAX_PACKAGE_BYTES = 50 * 1024 * 1024
MAX_ENTRY_BYTES = 16 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024
MAX_ENTRIES = 500
_DATA_URI = re.compile(r"data:(image/(?:png|jpeg|webp|gif|avif|svg\+xml));base64,([A-Za-z0-9+/=\r\n]+)", re.I)


@dataclass(frozen=True)
class ExperienceAsset:
    path: str
    data: bytes
    content_type: str
    sha256: str


@dataclass(frozen=True)
class ParsedExperience:
    source_schema: str
    package_key: str
    name: str
    description: str
    landing_html: str
    booking_html: str
    bindings: dict[str, Any]
    theme: dict[str, Any]
    assets: tuple[ExperienceAsset, ...]
    warnings: tuple[str, ...]


def _json_object(raw: bytes, name: str) -> dict[str, Any]:
    try:
        decoded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise APIError("EXPERIENCE_JSON_INVALID", f"{name} inválido.", 422) from exc
    if not isinstance(decoded, dict):
        raise APIError("EXPERIENCE_JSON_INVALID", f"{name} deve ser um objeto JSON.", 422)
    return cast(dict[str, Any], decoded)


def _safe_name(name: str) -> str:
    normalized = str(PurePosixPath(name.replace("\\", "/")))
    if not normalized or normalized.startswith("/") or ".." in PurePosixPath(normalized).parts:
        raise APIError("EXPERIENCE_ARCHIVE_PATH_INVALID", "O pacote contém caminho inseguro.", 422)
    return normalized


def _rewrite_asset_urls(html: str, package_key: str) -> str:
    base = f"/api/v1/public/assets/experience/{package_key}/assets/"
    output = str(html)
    # HTML attributes with quoted relative paths.
    output = re.sub(r"(?P<q>[\"'])\.\./assets/", lambda m: f"{m.group('q')}{base}", output, flags=re.I)
    output = re.sub(r"(?P<q>[\"'])assets/", lambda m: f"{m.group('q')}{base}", output, flags=re.I)
    # CSS url(...) may be quoted or unquoted; embedded Base64 extraction uses this form.
    output = re.sub(r"url\(\s*(?P<q>[\"']?)\.\./assets/", lambda m: f"url({m.group('q')}{base}", output, flags=re.I)
    output = re.sub(r"url\(\s*(?P<q>[\"']?)assets/", lambda m: f"url({m.group('q')}{base}", output, flags=re.I)
    return output


def _rewrite_binding_asset_urls(value: Any, package_key: str) -> Any:
    """Normaliza defaults/valores de bindings que apontam para assets do pacote."""
    base = f"/api/v1/public/assets/experience/{package_key}/assets/"
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("../assets/"):
            return base + stripped[len("../assets/") :]
        if stripped.startswith("assets/"):
            return base + stripped[len("assets/") :]
        return value
    if isinstance(value, list):
        return [_rewrite_binding_asset_urls(item, package_key) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_binding_asset_urls(item, package_key) for key, item in value.items()}
    return value


def _legacy_binding_definition(key: str) -> dict[str, Any]:
    lowered = key.lower()
    kind = "text"
    if any(token in lowered for token in ("logo", "image", "photo", "avatar", "hero.image")):
        kind = "image"
    elif any(token in lowered for token in ("whatsapp", "phone", "contact")):
        kind = "phone"
    elif any(token in lowered for token in ("url", "link", "instagram", "facebook")):
        kind = "url"
    elif any(token in lowered for token in ("color", "primary", "secondary", "accent", "background")):
        kind = "color"
    group = "Conteúdo"
    if lowered.startswith("business.") or lowered.startswith("brand."):
        group = "Identidade"
    elif lowered.startswith("landing.hero"):
        group = "Hero"
    elif lowered.startswith("landing.services"):
        group = "Serviços"
    elif lowered.startswith("booking."):
        group = "Agenda Pública"
    return {"type": kind, "label": key.replace(".", " · "), "group": group}


def _upgrade_legacy_bindings(html: str) -> tuple[str, dict[str, dict[str, Any]]]:
    """Preserva o HTML v1 e apenas adiciona bindings v2 onde o template já declarou edição."""
    definitions: dict[str, dict[str, Any]] = {}

    def add_binding(match: re.Match[str]) -> str:
        before, quote, key, after = match.group(1), match.group(2), match.group(3).strip(), match.group(4)
        definitions.setdefault(key, _legacy_binding_definition(key))
        if re.search(r"\bdata-sp-bind\s*=", before + after, re.I):
            return match.group(0)
        return f'{before}data-sp-edit={quote}{key}{quote} data-sp-bind={quote}{key}{quote}{after}'

    upgraded = re.sub(
        r"(<[^>]*?)data-sp-edit\s*=\s*([\"'])([^\"']+)\2([^>]*>)",
        add_binding,
        str(html),
        flags=re.I,
    )

    # Logos legados passam a herdar a identidade central sem reconstruir o layout.
    def bind_logo(match: re.Match[str]) -> str:
        tag = match.group(0)
        if re.search(r"\bdata-sp-bind\s*=", tag, re.I):
            return tag
        class_match = re.search(r"\bclass\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
        cls = class_match.group(2) if class_match else ""
        cls_lower = cls.lower()
        if "logo-dark" in cls_lower:
            key = "brand.logo_dark"
        elif "logo-light" in cls_lower or "brand" in cls_lower:
            key = "brand.logo"
        else:
            return tag
        definitions.setdefault(key, {"type": "image", "label": "Logo escuro" if key.endswith("dark") else "Logo claro", "group": "Identidade"})
        return re.sub(r"<img\b", f'<img data-sp-bind="{key}"', tag, count=1, flags=re.I)

    upgraded = re.sub(r"<img\b[^>]*>", bind_logo, upgraded, flags=re.I)
    return upgraded, definitions

def _extract_embedded_assets(html: str, prefix: str) -> tuple[str, list[ExperienceAsset]]:
    assets: list[ExperienceAsset] = []
    seen: dict[str, str] = {}
    ext_map = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif", "image/avif": "avif", "image/svg+xml": "svg"}

    def replace(match: re.Match[str]) -> str:
        media_type = match.group(1).lower()
        encoded = re.sub(r"\s+", "", match.group(2))
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError:
            return match.group(0)
        if len(data) < 4096:
            return match.group(0)
        sha = hashlib.sha256(data).hexdigest()
        path = seen.get(sha)
        if path is None:
            ext = ext_map.get(media_type, "bin")
            path = f"assets/{prefix}-{sha[:16]}.{ext}"
            seen[sha] = path
            assets.append(ExperienceAsset(path=path, data=data, content_type=media_type, sha256=sha))
        return f"../{path}"

    return _DATA_URI.sub(replace, html), assets


class ExperienceContractService:
    @staticmethod
    def parse_archive(data: bytes) -> ParsedExperience:
        if not data:
            raise APIError("EXPERIENCE_PACKAGE_EMPTY", "Pacote vazio.", 422)
        if len(data) > MAX_PACKAGE_BYTES:
            raise APIError("EXPERIENCE_PACKAGE_TOO_LARGE", "Pacote excede 50 MB.", 413)
        try:
            archive = ZipFile(BytesIO(data))
        except BadZipFile as exc:
            raise APIError("EXPERIENCE_PACKAGE_INVALID", "Arquivo ZIP inválido.", 422) from exc
        with archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTRIES:
                raise APIError("EXPERIENCE_PACKAGE_TOO_MANY_FILES", "Pacote possui arquivos demais.", 413)
            total = 0
            entries: dict[str, bytes] = {}
            for info in infos:
                if info.is_dir():
                    continue
                name = _safe_name(info.filename)
                if info.file_size > MAX_ENTRY_BYTES:
                    raise APIError("EXPERIENCE_ENTRY_TOO_LARGE", f"Arquivo muito grande: {name}", 413)
                total += int(info.file_size)
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise APIError("EXPERIENCE_PACKAGE_EXPANDED_TOO_LARGE", "Pacote expandido excede 80 MB.", 413)
                entries[name] = archive.read(info)

        if "experience.json" in entries:
            return ExperienceContractService._parse_v2(entries)
        if "template.json" in entries:
            return ExperienceContractService._parse_v1(entries)
        raise APIError("EXPERIENCE_MANIFEST_MISSING", "experience.json ou template.json ausente.", 422)

    @staticmethod
    def _parse_v2(entries: dict[str, bytes]) -> ParsedExperience:
        manifest = _json_object(entries["experience.json"], "experience.json")
        if manifest.get("schema") != EXPERIENCE_SCHEMA or int(manifest.get("version") or 0) != 2:
            raise APIError("EXPERIENCE_SCHEMA_INVALID", f"Use {EXPERIENCE_SCHEMA} version 2.", 422)
        package = manifest.get("package")
        pages = manifest.get("pages")
        files = manifest.get("files") or {}
        if not isinstance(package, dict) or not isinstance(pages, dict):
            raise APIError("EXPERIENCE_MANIFEST_INVALID", "package e pages são obrigatórios.", 422)
        key = str(package.get("key") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,127}", key):
            raise APIError("EXPERIENCE_KEY_INVALID", "package.key inválido.", 422)
        landing = pages.get("landing") or {}
        booking = pages.get("booking") or {}
        if not isinstance(landing, dict) or not isinstance(booking, dict):
            raise APIError("EXPERIENCE_PAGES_INVALID", "Landing e Booking precisam ser objetos.", 422)
        landing_entry = _safe_name(str(landing.get("entry") or "pages/landing.html"))
        booking_entry = _safe_name(str(booking.get("entry") or "pages/booking.html"))
        try:
            landing_html = entries[landing_entry].decode("utf-8")
            booking_html = entries[booking_entry].decode("utf-8")
        except (KeyError, UnicodeDecodeError) as exc:
            raise APIError("EXPERIENCE_PAGE_MISSING", "Landing ou Booking ausente/inválida.", 422) from exc
        bindings_path = _safe_name(str(files.get("bindings") or "bindings.json"))
        theme_path = _safe_name(str(files.get("theme") or "theme.json"))
        bindings = _rewrite_binding_asset_urls(
            _json_object(entries.get(bindings_path, b"{}"), bindings_path),
            key,
        )
        theme = _json_object(entries.get(theme_path, b"{}"), theme_path)
        assets: list[ExperienceAsset] = []
        for name, raw in entries.items():
            if not name.startswith("assets/"):
                continue
            media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            assets.append(ExperienceAsset(path=name, data=raw, content_type=media_type, sha256=hashlib.sha256(raw).hexdigest()))
        return ParsedExperience(
            source_schema=EXPERIENCE_SCHEMA,
            package_key=key,
            name=str(package.get("name") or key),
            description=str(package.get("description") or ""),
            landing_html=_rewrite_asset_urls(landing_html, key),
            booking_html=_rewrite_asset_urls(booking_html, key),
            bindings=bindings,
            theme=theme,
            assets=tuple(assets),
            warnings=(),
        )

    @staticmethod
    def _parse_v1(entries: dict[str, bytes]) -> ParsedExperience:
        manifest = _json_object(entries["template.json"], "template.json")
        if manifest.get("schema") != LEGACY_SCHEMA:
            raise APIError("EXPERIENCE_LEGACY_SCHEMA_INVALID", "template.json não usa o contrato legado suportado.", 422)
        package = manifest.get("package")
        if not isinstance(package, dict):
            raise APIError("EXPERIENCE_LEGACY_MANIFEST_INVALID", "package ausente no template legado.", 422)
        key = str(package.get("key") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,127}", key):
            raise APIError("EXPERIENCE_KEY_INVALID", "package.key inválido.", 422)
        try:
            landing = entries["landing.html"].decode("utf-8")
            booking = entries["agendamento.html"].decode("utf-8")
        except (KeyError, UnicodeDecodeError) as exc:
            raise APIError("EXPERIENCE_LEGACY_PAGES_MISSING", "O legado precisa conter landing.html e agendamento.html.", 422) from exc
        landing, landing_bindings = _upgrade_legacy_bindings(landing)
        booking, booking_bindings = _upgrade_legacy_bindings(booking)
        binding_definitions = {**landing_bindings, **booking_bindings}
        landing, a1 = _extract_embedded_assets(landing, "landing")
        booking, a2 = _extract_embedded_assets(booking, "booking")
        # PR63_FINAL_RUNTIME_FIX: preservar caminhos Landing/Booking mesmo quando
        # o conteúdo binário é idêntico. O HTML referencia o caminho lógico, não o SHA.
        assets_by_path: dict[str, ExperienceAsset] = {asset.path: asset for asset in [*a1, *a2]}
        return ParsedExperience(
            source_schema=LEGACY_SCHEMA,
            package_key=key,
            name=str(package.get("name") or key),
            description=str(package.get("description") or ""),
            landing_html=_rewrite_asset_urls(landing, key),
            booking_html=_rewrite_asset_urls(booking, key),
            bindings={"schema": "argws-bindings/v1", "version": 1, "bindings": binding_definitions},
            theme={"schema": "argws-theme-tokens/v1", "version": 1, "name": str(package.get("name") or key)},
            assets=tuple(assets_by_path.values()),
            warnings=(f"Pacote v1 migrado para Experience Contract v2; {len(assets_by_path)} asset(s) Base64 extraído(s) quando aplicável.", "Login legado foi ignorado; o Login é nativo/white-label no 2.4.0."),
        )
