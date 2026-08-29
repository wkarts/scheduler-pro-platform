from __future__ import annotations

from io import BytesIO
import base64
import json
import mimetypes
from pathlib import PurePosixPath
import re
from typing import Any
from zipfile import BadZipFile, ZipFile, ZipInfo, is_zipfile

from app.core.errors import APIError
from app.services.html_template_contract import HtmlTemplateContract
from app.services.experience_contract_service import EXPERIENCE_SCHEMA, ExperienceContractService

PACKAGE_SCHEMA = "scheduler-pro-template-package/v1"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_FILES = 500
VALID_SCOPES = {"GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL", "PLATFORM_DEFAULT"}
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,118}[a-z0-9]$")


def _issue(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def _safe_name(raw: str) -> str | None:
    if not raw or "\\" in raw or raw.startswith("/") or ":" in raw.split("/", 1)[0]:
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return str(path)


class HtmlTemplatePackageService:
    """Valida o pacote ZIP autoral usado como unidade canônica de templates.

    O importador aceita o Experience Contract v2 (canônico) e o Template Package v1 (legado).
    Em ambos os casos, Landing e Agenda permanecem documentos HTML completos.
    Assets do v2 são incorporados ao HTML da biblioteca global para manter o pacote autocontido.
    """

    @classmethod
    def _parse_v1(cls, archive: bytes) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        result: dict[str, Any] = {
            "valid": False,
            "schema": PACKAGE_SCHEMA,
            "errors": errors,
            "warnings": warnings,
            "package": {},
            "surfaces": {},
            "documents": {},
        }
        if not archive:
            errors.append(_issue("package", "PACKAGE_FILE_REQUIRED", "Selecione um pacote .zip."))
            return result
        if len(archive) > MAX_ARCHIVE_BYTES:
            errors.append(_issue("package", "PACKAGE_ARCHIVE_TOO_LARGE", "O pacote ZIP excede 50 MB."))
            return result
        if not is_zipfile(BytesIO(archive)):
            errors.append(_issue("package", "PACKAGE_ZIP_INVALID", "O arquivo não é um ZIP válido."))
            return result

        try:
            with ZipFile(BytesIO(archive)) as zipped:
                infos = [member for member in zipped.infolist() if not member.is_dir()]
                if len(infos) > MAX_FILES:
                    errors.append(_issue("package", "PACKAGE_TOO_MANY_FILES", "O pacote possui arquivos demais."))
                    return result
                total = 0
                names: dict[str, ZipInfo] = {}
                for member in infos:
                    safe = _safe_name(member.filename)
                    if safe is None:
                        errors.append(
                            _issue(
                                "package.files",
                                "PACKAGE_PATH_UNSAFE",
                                f"Caminho inválido no ZIP: {member.filename}.",
                            )
                        )
                        continue
                    if safe in names:
                        errors.append(
                            _issue(
                                "package.files",
                                "PACKAGE_FILE_DUPLICATED",
                                f"Arquivo duplicado no ZIP: {safe}.",
                            )
                        )
                        continue
                    if member.flag_bits & 0x1:
                        errors.append(
                            _issue(
                                "package.files",
                                "PACKAGE_ENCRYPTED_FILE",
                                f"Arquivo criptografado não permitido: {safe}.",
                            )
                        )
                        continue
                    file_type = (member.external_attr >> 16) & 0o170000
                    if file_type == 0o120000:
                        errors.append(
                            _issue(
                                "package.files",
                                "PACKAGE_SYMLINK_FORBIDDEN",
                                f"Link simbólico não permitido: {safe}.",
                            )
                        )
                        continue
                    if member.file_size > MAX_FILE_BYTES:
                        errors.append(
                            _issue(
                                "package.files",
                                "PACKAGE_FILE_TOO_LARGE",
                                f"Arquivo excede 16 MB: {safe}.",
                            )
                        )
                        continue
                    total += int(member.file_size)
                    names[safe] = member
                if total > MAX_UNCOMPRESSED_BYTES:
                    errors.append(
                        _issue(
                            "package",
                            "PACKAGE_UNCOMPRESSED_TOO_LARGE",
                            "O conteúdo descompactado excede 80 MB.",
                        )
                    )
                if errors:
                    return result

                manifest_info = names.get("template.json")
                if manifest_info is None:
                    errors.append(
                        _issue(
                            "template.json",
                            "PACKAGE_MANIFEST_REQUIRED",
                            "O pacote precisa conter template.json na raiz.",
                        )
                    )
                    return result
                try:
                    manifest = json.loads(zipped.read(manifest_info).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors.append(
                        _issue(
                            "template.json",
                            "PACKAGE_MANIFEST_INVALID",
                            f"template.json inválido: {exc}.",
                        )
                    )
                    return result
                if not isinstance(manifest, dict) or manifest.get("schema") != PACKAGE_SCHEMA:
                    errors.append(
                        _issue(
                            "template.json.schema",
                            "PACKAGE_SCHEMA_INVALID",
                            f"Use schema={PACKAGE_SCHEMA}.",
                        )
                    )
                    return result
                package = manifest.get("package")
                if not isinstance(package, dict):
                    errors.append(
                        _issue(
                            "template.json.package",
                            "PACKAGE_METADATA_REQUIRED",
                            "Informe o objeto package no manifesto.",
                        )
                    )
                    return result

                key = str(package.get("key") or "").strip().lower()
                name = str(package.get("name") or "").strip()
                scope = str(package.get("scope") or "INTERNAL").strip().upper()
                segment = str(package.get("segment") or "").strip() or None
                description = str(package.get("description") or "").strip() or None
                if len(key) < 2 or not KEY_RE.fullmatch(key):
                    errors.append(
                        _issue(
                            "template.json.package.key",
                            "PACKAGE_KEY_INVALID",
                            "Use uma chave minúscula com números e hífen.",
                        )
                    )
                if len(name) < 2 or len(name) > 180:
                    errors.append(
                        _issue(
                            "template.json.package.name",
                            "PACKAGE_NAME_INVALID",
                            "Informe um nome entre 2 e 180 caracteres.",
                        )
                    )
                if scope not in VALID_SCOPES:
                    errors.append(
                        _issue(
                            "template.json.package.scope",
                            "PACKAGE_SCOPE_INVALID",
                            "Escopo deve ser GLOBAL, SELECTED, EXCLUSIVE, INTERNAL ou PLATFORM_DEFAULT.",
                        )
                    )

                surfaces = package.get("surfaces")
                if not isinstance(surfaces, dict):
                    errors.append(
                        _issue(
                            "template.json.package.surfaces",
                            "PACKAGE_SURFACES_REQUIRED",
                            "Informe package.surfaces.",
                        )
                    )
                    return result

                documents: dict[str, str] = {}
                summaries: dict[str, Any] = {}
                expected = {
                    "landing": ("LANDING", "/pagina"),
                    "booking": ("BOOKING", "/agendar"),
                    "login": ("LOGIN", "/login"),
                }
                for manifest_key, (surface, canonical_route) in expected.items():
                    raw = surfaces.get(manifest_key)
                    if raw is None:
                        continue
                    path = f"template.json.package.surfaces.{manifest_key}"
                    if not isinstance(raw, dict):
                        errors.append(
                            _issue(
                                path,
                                "PACKAGE_SURFACE_INVALID",
                                "A superfície deve ser um objeto.",
                            )
                        )
                        continue
                    if str(raw.get("surface") or "").strip().upper() != surface:
                        errors.append(
                            _issue(
                                f"{path}.surface",
                                "PACKAGE_SURFACE_MISMATCH",
                                f"Use surface={surface}.",
                            )
                        )
                    if str(raw.get("renderer") or "").strip().upper() != "HTML":
                        errors.append(
                            _issue(
                                f"{path}.renderer",
                                "PACKAGE_RENDERER_INVALID",
                                "O novo padrão autoral usa renderer=HTML.",
                            )
                        )
                    minimum_version = 1 if surface == "LOGIN" else 2
                    try:
                        surface_version = float(raw.get("version") or 0)
                    except (TypeError, ValueError):
                        surface_version = 0
                    if surface_version < minimum_version:
                        errors.append(
                            _issue(
                                f"{path}.version",
                                "PACKAGE_SURFACE_VERSION_INVALID",
                                f"Use version {minimum_version} ou superior para {surface}.",
                            )
                        )
                    route = str(raw.get("route") or "").strip()
                    if route and route != canonical_route:
                        errors.append(
                            _issue(
                                f"{path}.route",
                                "PACKAGE_ROUTE_INVALID",
                                f"A rota canônica desta superfície é {canonical_route}.",
                            )
                        )
                    entry = _safe_name(str(raw.get("entry") or ""))
                    if not entry:
                        errors.append(
                            _issue(
                                f"{path}.entry",
                                "PACKAGE_ENTRY_INVALID",
                                "Informe um arquivo HTML relativo dentro do ZIP.",
                            )
                        )
                        continue
                    entry_info = names.get(entry)
                    if entry_info is None:
                        errors.append(
                            _issue(
                                f"{path}.entry",
                                "PACKAGE_ENTRY_NOT_FOUND",
                                f"Arquivo não encontrado no pacote: {entry}.",
                            )
                        )
                        continue
                    try:
                        html_document = zipped.read(entry_info).decode("utf-8")
                    except UnicodeDecodeError:
                        errors.append(
                            _issue(
                                f"{path}.entry",
                                "PACKAGE_ENTRY_ENCODING_INVALID",
                                f"Use UTF-8 em {entry}.",
                            )
                        )
                        continue
                    documents[surface] = html_document
                    summaries[manifest_key] = {
                        "surface": surface,
                        "entry": entry,
                        "route": canonical_route,
                        "bytes": len(html_document.encode("utf-8")),
                        "version": int(raw.get("version") or 0),
                    }

                if not documents:
                    errors.append(
                        _issue(
                            "template.json.package.surfaces",
                            "PACKAGE_SURFACE_EMPTY",
                            "Inclua landing.html, agendamento.html, login.html ou uma combinação válida.",
                        )
                    )
                if errors:
                    result["package"] = {
                        "key": key,
                        "name": name,
                        "scope": scope,
                        "segment": segment,
                        "description": description,
                    }
                    result["surfaces"] = summaries
                    return result

                pair = HtmlTemplateContract.validate_family(
                    landing_html=documents.get("LANDING"),
                    booking_html=documents.get("BOOKING"),
                    login_html=documents.get("LOGIN"),
                )
                for item in pair.get("errors", []):
                    errors.append({**item, "path": f"html.{item['path']}"})
                for item in pair.get("warnings", []):
                    warnings.append({**item, "path": f"html.{item['path']}"})
                detected_key = str(pair.get("template_key") or "")
                if detected_key and key and detected_key != key:
                    errors.append(
                        _issue(
                            "template.json.package.key",
                            "PACKAGE_HTML_KEY_MISMATCH",
                            f"O manifesto usa {key}, mas o HTML declara {detected_key}.",
                        )
                    )
                if len(documents) == 1:
                    warnings.append(
                        _issue(
                            "template.json.package.surfaces",
                            "PACKAGE_PAIR_RECOMMENDED",
                            "O pacote é válido, mas uma família completa normalmente contém Landing, Agenda Pública e Login.",
                        )
                    )

                result.update(
                    {
                        "valid": not errors,
                        "package": {
                            "key": key,
                            "name": name,
                            "description": description,
                            "segment": segment,
                            "scope": scope,
                            "default_for_new_tenants": bool(
                                package.get("default_for_new_tenants", False)
                            ),
                        },
                        "surfaces": summaries,
                        "documents": documents,
                        "html_validation": pair,
                        "archive_bytes": len(archive),
                        "uncompressed_bytes": total,
                        "file_count": len(infos),
                    }
                )
                return result
        except BadZipFile:
            errors.append(
                _issue(
                    "package",
                    "PACKAGE_ZIP_INVALID",
                    "O arquivo ZIP está corrompido.",
                )
            )
            return result

    @staticmethod
    def _inline_v2_assets(html_document: str, package_key: str, assets: tuple[Any, ...]) -> str:
        output = str(html_document)
        base = f"/api/v1/public/assets/experience/{package_key}/assets/"
        for asset in assets:
            logical = str(asset.path)
            if not logical.startswith("assets/"):
                continue
            name = logical[len("assets/") :]
            media_type = str(asset.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream")
            data_uri = f"data:{media_type};base64,{base64.b64encode(asset.data).decode('ascii')}"
            output = output.replace(base + name, data_uri)
        return output

    @classmethod
    def _parse_v2(cls, archive: bytes) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        result: dict[str, Any] = {
            "valid": False,
            "schema": EXPERIENCE_SCHEMA,
            "errors": errors,
            "warnings": warnings,
            "package": {},
            "surfaces": {},
            "documents": {},
        }
        if not archive:
            errors.append(_issue("package", "PACKAGE_FILE_REQUIRED", "Selecione um pacote .zip."))
            return result
        if len(archive) > MAX_ARCHIVE_BYTES:
            errors.append(_issue("package", "PACKAGE_ARCHIVE_TOO_LARGE", "O pacote ZIP excede 50 MB."))
            return result
        try:
            parsed = ExperienceContractService.parse_archive(archive)
            if parsed.source_schema != EXPERIENCE_SCHEMA:
                return cls._parse_v1(archive)
            with ZipFile(BytesIO(archive)) as zipped:
                infos = [member for member in zipped.infolist() if not member.is_dir()]
                manifest = json.loads(zipped.read("experience.json").decode("utf-8"))
                total = sum(int(item.file_size) for item in infos)
            package = manifest.get("package") or {}
            pages = manifest.get("pages") or {}
            scope = str(package.get("scope") or "INTERNAL").upper()
            if scope not in VALID_SCOPES:
                errors.append(_issue("experience.json.package.scope", "PACKAGE_SCOPE_INVALID", "Escopo inválido no Experience Package."))
            documents = {
                "LANDING": cls._inline_v2_assets(parsed.landing_html, parsed.package_key, parsed.assets),
                "BOOKING": cls._inline_v2_assets(parsed.booking_html, parsed.package_key, parsed.assets),
            }
            # A biblioteca global não possui storage de assets por pacote. Por isso
            # defaults de bindings visuais também precisam ficar autocontidos.
            experience_bindings = json.loads(json.dumps(parsed.bindings, ensure_ascii=False))
            asset_base = f"/api/v1/public/assets/experience/{parsed.package_key}/assets/"
            asset_data = {}
            for asset in parsed.assets:
                logical = str(asset.path)
                if logical.startswith("assets/"):
                    name = logical[len("assets/") :]
                    media_type = str(asset.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream")
                    asset_data[asset_base + name] = f"data:{media_type};base64,{base64.b64encode(asset.data).decode('ascii')}"
            def inline_binding(value: Any) -> Any:
                if isinstance(value, str):
                    return asset_data.get(value, value)
                if isinstance(value, list):
                    return [inline_binding(item) for item in value]
                if isinstance(value, dict):
                    return {key: inline_binding(item) for key, item in value.items()}
                return value
            experience_bindings = inline_binding(experience_bindings)
            pair = HtmlTemplateContract.validate_family(
                landing_html=documents["LANDING"],
                booking_html=documents["BOOKING"],
            )
            for item in pair.get("errors", []):
                errors.append({**item, "path": f"html.{item['path']}"})
            for item in pair.get("warnings", []):
                warnings.append({**item, "path": f"html.{item['path']}"})
            for message in parsed.warnings:
                warnings.append(_issue("experience", "EXPERIENCE_MIGRATION_WARNING", str(message)))
            summaries: dict[str, Any] = {}
            for key, surface, route in (("landing", "LANDING", "/pagina"), ("booking", "BOOKING", "/agendar")):
                page = pages.get(key) or {}
                entry = str(page.get("entry") or f"pages/{key}.html")
                summaries[key] = {
                    "surface": surface,
                    "entry": entry,
                    "route": route,
                    "bytes": len(documents[surface].encode("utf-8")),
                    "version": 2,
                }
            result.update(
                {
                    "valid": not errors,
                    "package": {
                        "key": parsed.package_key,
                        "name": parsed.name,
                        "description": parsed.description or None,
                        "segment": str(package.get("segment") or "").strip() or None,
                        "scope": scope,
                        "default_for_new_tenants": bool(package.get("default_for_new_tenants", False)),
                        "package_version": str(package.get("package_version") or "2"),
                        "source_schema": EXPERIENCE_SCHEMA,
                    },
                    "surfaces": summaries,
                    "documents": documents,
                    "html_validation": pair,
                    "experience": {
                        "schema": EXPERIENCE_SCHEMA,
                        "version": 2,
                        "bindings": experience_bindings,
                        "theme": parsed.theme,
                        "package_version": str(package.get("package_version") or "2"),
                        "capabilities": list(package.get("capabilities") or []),
                        "authoring_mode": str(package.get("authoring_mode") or "runtime-html"),
                        "assets_inlined": len(parsed.assets),
                    },
                    "archive_bytes": len(archive),
                    "uncompressed_bytes": total,
                    "file_count": len(infos),
                }
            )
            return result
        except APIError as exc:
            details = exc.details if isinstance(exc.details, dict) else {}
            nested = details.get("errors") if isinstance(details, dict) else None
            if isinstance(nested, list):
                errors.extend(nested)
            else:
                errors.append(_issue("experience", exc.code, exc.message))
            return result
        except (BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(_issue("experience.json", "EXPERIENCE_PACKAGE_INVALID", f"Experience Package inválido: {exc}."))
            return result

    @classmethod
    def _parse(cls, archive: bytes) -> dict[str, Any]:
        if archive and len(archive) <= MAX_ARCHIVE_BYTES and is_zipfile(BytesIO(archive)):
            try:
                with ZipFile(BytesIO(archive)) as zipped:
                    names = {_safe_name(item.filename) for item in zipped.infolist() if not item.is_dir()}
                if "experience.json" in names:
                    return cls._parse_v2(archive)
            except BadZipFile:
                pass
        return cls._parse_v1(archive)

    @classmethod
    def validate(cls, archive: bytes) -> dict[str, Any]:
        parsed = cls._parse(archive)
        return {key: value for key, value in parsed.items() if key != "documents"}

    @classmethod
    def ensure(cls, archive: bytes) -> dict[str, Any]:
        parsed = cls._parse(archive)
        if not parsed["valid"]:
            raise APIError(
                "HTML_TEMPLATE_PACKAGE_INVALID",
                "O pacote não atende ao padrão de templates do Scheduler Pro.",
                422,
                details={
                    key: value
                    for key, value in parsed.items()
                    if key != "documents"
                },
            )
        return parsed
