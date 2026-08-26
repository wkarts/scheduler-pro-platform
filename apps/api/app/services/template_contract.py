from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from app.core.errors import APIError

CONTRACT_NAME = "Scheduler Pro Template Contract"
CONTRACT_SCHEMA = "scheduler-pro-template-package/v1"
CONTRACT_VERSION = 1
PACKAGE_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,118}[a-z0-9]$")
SURFACES = {"LANDING", "BOOKING"}
SCOPES = {"GLOBAL", "SELECTED", "EXCLUSIVE", "INTERNAL"}

SUPPORTED_LANDING_BLOCKS = {
    "section",
    "container",
    "columns",
    "grid",
    "hero",
    "title",
    "subtitle",
    "text",
    "logo",
    "image",
    "gallery",
    "video",
    "button",
    "whatsapp_button",
    "social",
    "divider",
    "spacer",
    "card",
    "cards",
    "services",
    "professionals",
    "booking",
    "calendar",
    "form",
    "business_hours",
    "address",
    "map",
    "contact",
    "faq",
    "testimonials",
    "cta",
    "notices",
    "policies",
    "footer",
}
BOOKING_LAYOUT_VALUES: dict[str, set[str]] = {
    "service_selector": {"cards", "select", "compact"},
    "professional_selector": {"cards", "select", "compact"},
    "calendar": {"month_days", "week_days", "date_input"},
    "time_selector": {"chips", "grid", "select"},
    "customer_form": {"compact", "stacked", "cards"},
}


def _issue(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


class TemplateContract:
    """Contrato canônico para Landing Page e Página de Agendamento.

    A validação é centralizada aqui para que importação, catálogo global,
    rascunho da Landing e aplicação da página de agendamento não mantenham
    regras divergentes.
    """

    @staticmethod
    def _surface(value: str) -> str:
        surface = value.strip().upper()
        if surface not in SURFACES:
            raise APIError("TEMPLATE_SURFACE_INVALID", "Área de modelo inválida.", 422)
        return surface

    @classmethod
    def validate_content(
        cls,
        surface: str,
        content: Any,
        *,
        strict: bool = True,
    ) -> dict[str, Any]:
        normalized_surface = cls._surface(surface)
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        if not isinstance(content, dict):
            errors.append(_issue("content", "CONTENT_OBJECT_REQUIRED", "O conteúdo do modelo deve ser um objeto JSON."))
            return {
                "valid": False,
                "surface": normalized_surface,
                "errors": errors,
                "warnings": warnings,
            }

        if normalized_surface == "LANDING":
            cls._validate_landing(content, strict=strict, errors=errors, warnings=warnings)
        else:
            cls._validate_booking(content, strict=strict, errors=errors, warnings=warnings)
        return {
            "valid": not errors,
            "surface": normalized_surface,
            "errors": errors,
            "warnings": warnings,
        }

    @staticmethod
    def _validate_landing(
        content: dict[str, Any],
        *,
        strict: bool,
        errors: list[dict[str, str]],
        warnings: list[dict[str, str]],
    ) -> None:
        version = content.get("version")
        if not isinstance(version, int) or isinstance(version, bool):
            errors.append(_issue("content.version", "LANDING_VERSION_REQUIRED", "Informe uma versão numérica da Landing Page."))
        elif strict and version < 2:
            errors.append(_issue("content.version", "LANDING_VERSION_UNSUPPORTED", "Novos modelos de Landing Page devem usar o formato versão 2 ou superior."))

        global_styles = content.get("global_styles")
        if strict and not isinstance(global_styles, dict):
            errors.append(_issue("content.global_styles", "LANDING_GLOBAL_STYLES_REQUIRED", "Defina global_styles para identidade visual e contraste."))
        elif global_styles is not None and not isinstance(global_styles, dict):
            errors.append(_issue("content.global_styles", "LANDING_GLOBAL_STYLES_INVALID", "global_styles deve ser um objeto."))

        seo = content.get("seo")
        if strict and not isinstance(seo, dict):
            errors.append(_issue("content.seo", "LANDING_SEO_REQUIRED", "Defina o objeto seo, mesmo que inicialmente vazio."))
        elif seo is not None and not isinstance(seo, dict):
            errors.append(_issue("content.seo", "LANDING_SEO_INVALID", "seo deve ser um objeto."))

        blocks = content.get("blocks")
        if blocks is None and not strict and isinstance(content.get("sections"), list):
            warnings.append(_issue("content.sections", "LANDING_LEGACY_FORMAT", "Conteúdo legado aceito apenas por compatibilidade. Novos modelos devem usar blocks."))
            return
        if not isinstance(blocks, list):
            errors.append(_issue("content.blocks", "LANDING_BLOCKS_REQUIRED", "A Landing Page deve possuir uma lista blocks."))
            return
        if strict and not blocks:
            errors.append(_issue("content.blocks", "LANDING_BLOCKS_EMPTY", "O modelo precisa possuir ao menos um bloco."))
            return

        ids: set[str] = set()
        booking_integration = False
        for index, raw_block in enumerate(blocks):
            path = f"content.blocks[{index}]"
            if not isinstance(raw_block, dict):
                errors.append(_issue(path, "LANDING_BLOCK_INVALID", "Cada bloco deve ser um objeto."))
                continue
            block_id = str(raw_block.get("id") or "").strip()
            block_type = str(raw_block.get("type") or "").strip()
            if not block_id:
                errors.append(_issue(f"{path}.id", "LANDING_BLOCK_ID_REQUIRED", "Cada bloco precisa de um id estável."))
            elif block_id in ids:
                errors.append(_issue(f"{path}.id", "LANDING_BLOCK_ID_DUPLICATED", "Os ids dos blocos devem ser únicos."))
            else:
                ids.add(block_id)
            if not block_type:
                errors.append(_issue(f"{path}.type", "LANDING_BLOCK_TYPE_REQUIRED", "Cada bloco precisa informar type."))
            elif block_type not in SUPPORTED_LANDING_BLOCKS:
                errors.append(_issue(f"{path}.type", "LANDING_BLOCK_TYPE_UNSUPPORTED", f"Bloco não suportado pelo renderer público: {block_type}."))
            if block_type in {"booking", "calendar", "form"}:
                booking_integration = True
            props = raw_block.get("props")
            if not isinstance(props, dict):
                errors.append(_issue(f"{path}.props", "LANDING_BLOCK_PROPS_REQUIRED", "props deve ser um objeto."))
            style = raw_block.get("style", {})
            if not isinstance(style, dict):
                errors.append(_issue(f"{path}.style", "LANDING_BLOCK_STYLE_INVALID", "style deve ser um objeto."))
            responsive = raw_block.get("responsive", {})
            if not isinstance(responsive, dict):
                errors.append(_issue(f"{path}.responsive", "LANDING_BLOCK_RESPONSIVE_INVALID", "responsive deve ser um objeto."))
                continue
            for device in ("desktop", "tablet", "mobile"):
                device_style = responsive.get(device, {})
                if not isinstance(device_style, dict):
                    errors.append(_issue(f"{path}.responsive.{device}", "LANDING_RESPONSIVE_DEVICE_INVALID", f"responsive.{device} deve ser um objeto."))
            hidden = responsive.get("hidden", {})
            if not isinstance(hidden, dict):
                errors.append(_issue(f"{path}.responsive.hidden", "LANDING_RESPONSIVE_HIDDEN_INVALID", "responsive.hidden deve ser um objeto."))
            else:
                for device in ("desktop", "tablet", "mobile"):
                    if device in hidden and not isinstance(hidden[device], bool):
                        errors.append(_issue(f"{path}.responsive.hidden.{device}", "LANDING_RESPONSIVE_HIDDEN_VALUE_INVALID", "A visibilidade responsiva deve ser booleana."))
        if blocks and not booking_integration:
            warnings.append(_issue("content.blocks", "LANDING_BOOKING_BLOCK_RECOMMENDED", "O renderer adicionará a agenda ao final, mas modelos oficiais devem preferir um bloco booking, calendar ou form explícito."))

    @staticmethod
    def _validate_booking(
        content: dict[str, Any],
        *,
        strict: bool,
        errors: list[dict[str, str]],
        warnings: list[dict[str, str]],
    ) -> None:
        version = content.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            errors.append(_issue("content.version", "BOOKING_VERSION_REQUIRED", "A Página de Agendamento precisa de version >= 1."))
        declared_surface = str(content.get("surface") or "").strip().upper()
        if strict and declared_surface != "BOOKING":
            errors.append(_issue("content.surface", "BOOKING_SURFACE_REQUIRED", "Novos modelos de agendamento devem declarar surface=BOOKING."))
        elif declared_surface and declared_surface != "BOOKING":
            errors.append(_issue("content.surface", "BOOKING_SURFACE_INVALID", "surface deve ser BOOKING."))

        global_styles = content.get("global_styles")
        if not isinstance(global_styles, dict):
            errors.append(_issue("content.global_styles", "BOOKING_GLOBAL_STYLES_REQUIRED", "Defina global_styles da Página de Agendamento."))
        layout = content.get("layout")
        if not isinstance(layout, dict):
            errors.append(_issue("content.layout", "BOOKING_LAYOUT_REQUIRED", "Defina o objeto layout."))
        else:
            for key, allowed in BOOKING_LAYOUT_VALUES.items():
                if key not in layout:
                    continue
                layout_value = str(layout[key])
                if layout_value not in allowed:
                    errors.append(_issue(f"content.layout.{key}", "BOOKING_LAYOUT_VALUE_UNSUPPORTED", f"Valor não suportado: {layout_value}."))
            if "mobile_sticky_action" in layout and not isinstance(layout["mobile_sticky_action"], bool):
                errors.append(_issue("content.layout.mobile_sticky_action", "BOOKING_LAYOUT_BOOLEAN_REQUIRED", "mobile_sticky_action deve ser booleano."))

        copy = content.get("copy")
        if not isinstance(copy, dict):
            errors.append(_issue("content.copy", "BOOKING_COPY_REQUIRED", "Defina o objeto copy com os textos da experiência de agendamento."))
        else:
            for key in ("title", "subtitle", "success"):
                copy_value = copy.get(key)
                if strict and (not isinstance(copy_value, str) or not copy_value.strip()):
                    errors.append(_issue(f"content.copy.{key}", "BOOKING_COPY_VALUE_REQUIRED", f"Informe copy.{key}."))
        if isinstance(global_styles, dict) and "muted" not in global_styles:
            warnings.append(_issue("content.global_styles.muted", "BOOKING_MUTED_COLOR_RECOMMENDED", "Defina a cor muted para manter os subtítulos legíveis."))

    @classmethod
    def ensure_content(
        cls,
        surface: str,
        content: Any,
        *,
        strict: bool = True,
    ) -> dict[str, Any]:
        report = cls.validate_content(surface, content, strict=strict)
        if not report["valid"]:
            raise APIError(
                "TEMPLATE_CONTRACT_INVALID",
                "O conteúdo não atende ao contrato de modelos do Scheduler Pro.",
                422,
                details=report,
            )
        return report

    @classmethod
    def validate_package(cls, bundle: Any) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        surface_reports: dict[str, Any] = {}
        if not isinstance(bundle, dict):
            errors.append(_issue("bundle", "PACKAGE_OBJECT_REQUIRED", "O pacote deve ser um objeto JSON."))
            return {"valid": False, "schema": CONTRACT_SCHEMA, "errors": errors, "warnings": warnings, "surfaces": surface_reports}
        if bundle.get("schema") != CONTRACT_SCHEMA:
            errors.append(_issue("schema", "PACKAGE_SCHEMA_INVALID", f"Use schema={CONTRACT_SCHEMA}."))
        package = bundle.get("package")
        if not isinstance(package, dict):
            errors.append(_issue("package", "PACKAGE_METADATA_REQUIRED", "O pacote precisa do objeto package."))
            return {"valid": False, "schema": CONTRACT_SCHEMA, "errors": errors, "warnings": warnings, "surfaces": surface_reports}

        key = str(package.get("key") or "").strip().lower()
        if len(key) < 2 or not PACKAGE_KEY_PATTERN.fullmatch(key):
            errors.append(_issue("package.key", "PACKAGE_KEY_INVALID", "Use chave em minúsculas, com números e hífen, entre 2 e 120 caracteres."))
        name = str(package.get("name") or "").strip()
        if len(name) < 2 or len(name) > 180:
            errors.append(_issue("package.name", "PACKAGE_NAME_INVALID", "Informe um nome entre 2 e 180 caracteres."))
        scope = str(package.get("scope") or "INTERNAL").strip().upper()
        if scope not in SCOPES:
            errors.append(_issue("package.scope", "PACKAGE_SCOPE_INVALID", "Escopo deve ser GLOBAL, SELECTED, EXCLUSIVE ou INTERNAL."))
        if scope == "EXCLUSIVE" and not str(package.get("exclusive_tenant_id") or "").strip():
            warnings.append(_issue("package.exclusive_tenant_id", "PACKAGE_EXCLUSIVE_TARGET_PENDING", "O cliente exclusivo pode ser escolhido na Central de Importação."))

        surfaces = package.get("surfaces")
        if not isinstance(surfaces, dict):
            errors.append(_issue("package.surfaces", "PACKAGE_SURFACES_REQUIRED", "Informe package.surfaces."))
        else:
            found = 0
            for package_key, surface in (("landing", "LANDING"), ("booking", "BOOKING")):
                content = surfaces.get(package_key)
                if content is None:
                    continue
                found += 1
                report = cls.validate_content(surface, content, strict=True)
                surface_reports[package_key] = report
                for item in report["errors"]:
                    errors.append({**item, "path": f"package.surfaces.{package_key}.{item['path'].removeprefix('content.')}"})
                for item in report["warnings"]:
                    warnings.append({**item, "path": f"package.surfaces.{package_key}.{item['path'].removeprefix('content.')}"})
            if found == 0:
                errors.append(_issue("package.surfaces", "PACKAGE_SURFACE_EMPTY", "Inclua ao menos landing ou booking."))
            elif found == 1:
                warnings.append(_issue("package.surfaces", "PACKAGE_PAIR_RECOMMENDED", "O pacote é válido, mas uma família completa normalmente contém Landing Page e Página de Agendamento."))
        return {
            "valid": not errors,
            "schema": CONTRACT_SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "key": key,
            "name": name,
            "scope": scope,
            "errors": errors,
            "warnings": warnings,
            "surfaces": surface_reports,
        }

    @classmethod
    def ensure_package(cls, bundle: Any) -> dict[str, Any]:
        report = cls.validate_package(bundle)
        if not report["valid"]:
            raise APIError(
                "TEMPLATE_PACKAGE_INVALID",
                "O pacote importado não atende ao contrato de modelos do Scheduler Pro.",
                422,
                details=report,
            )
        return report

    @staticmethod
    def example_package() -> dict[str, Any]:
        return {
            "schema": CONTRACT_SCHEMA,
            "package": {
                "key": "modelo-negocio-generico",
                "name": "Modelo de Negócio Genérico",
                "description": "Família de exemplo compatível com Landing Page e Página de Agendamento.",
                "segment": "generico",
                "scope": "INTERNAL",
                "default_for_new_tenants": False,
                "surfaces": {
                    "landing": {
                        "version": 2,
                        "title": "Seu negócio",
                        "global_styles": {
                            "primary": "#2563eb",
                            "secondary": "#0f172a",
                            "accent": "#7c3aed",
                            "background": "#ffffff",
                            "text": "#17233a",
                            "radius": 20,
                        },
                        "seo": {"title": "Seu negócio", "description": "Agende online."},
                        "blocks": [
                            {
                                "id": "hero-1",
                                "type": "hero",
                                "props": {"eyebrow": "Atendimento", "title": "Seu negócio", "text": "Apresente sua proposta de valor.", "cta": "Agendar agora", "image": ""},
                                "style": {},
                                "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
                            },
                            {
                                "id": "booking-1",
                                "type": "booking",
                                "props": {"title": "Escolha seu horário", "subtitle": "Agende em poucos passos."},
                                "style": {},
                                "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
                            },
                            {
                                "id": "footer-1",
                                "type": "footer",
                                "props": {"text": "Atendimento com Scheduler Pro."},
                                "style": {},
                                "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
                            },
                        ],
                    },
                    "booking": {
                        "version": 1,
                        "surface": "BOOKING",
                        "global_styles": {
                            "primary": "#2563eb",
                            "secondary": "#0f172a",
                            "accent": "#7c3aed",
                            "background": "#f5f7fb",
                            "surface": "#ffffff",
                            "text": "#17233a",
                            "muted": "#64748b",
                            "radius": 20,
                        },
                        "layout": {
                            "service_selector": "cards",
                            "professional_selector": "cards",
                            "calendar": "month_days",
                            "time_selector": "chips",
                            "customer_form": "compact",
                            "mobile_sticky_action": True,
                        },
                        "copy": {
                            "eyebrow": "Agendamento online",
                            "title": "Escolha seu horário",
                            "subtitle": "Selecione o atendimento e a melhor disponibilidade.",
                            "success": "Seu horário foi reservado.",
                        },
                    },
                },
            },
        }

    @classmethod
    def descriptor(cls) -> dict[str, Any]:
        return {
            "name": CONTRACT_NAME,
            "schema": CONTRACT_SCHEMA,
            "version": CONTRACT_VERSION,
            "file_name_pattern": "*.scheduler-pro-template.json",
            "canonical_import_location": "Control Plane > Modelos & Suporte > Importar Modelos",
            "surfaces": {
                "LANDING": {
                    "content_version": 2,
                    "required": ["version", "global_styles", "seo", "blocks"],
                    "supported_blocks": sorted(SUPPORTED_LANDING_BLOCKS),
                },
                "BOOKING": {
                    "content_version": 1,
                    "required": ["version", "surface", "global_styles", "layout", "copy"],
                    "layout_values": {key: sorted(values) for key, values in BOOKING_LAYOUT_VALUES.items()},
                },
            },
            "scope_values": sorted(SCOPES),
            "example": deepcopy(cls.example_package()),
        }
