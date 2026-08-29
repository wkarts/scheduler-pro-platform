from __future__ import annotations

from copy import deepcopy
from html.parser import HTMLParser
import re
from typing import Any

from app.core.errors import APIError

HTML_CONTRACT_NAME = "Scheduler Pro HTML Template Contract"
HTML_CONTRACT_SCHEMA = "scheduler-pro-html-template/v1"
HTML_CONTRACT_VERSION = 1
HTML_MAX_BYTES = 4 * 1024 * 1024
TEMPLATE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,118}[a-z0-9]$")
SURFACE_META_TO_INTERNAL = {
    "landing": "LANDING",
    "public-booking": "BOOKING",
    "booking": "BOOKING",
    "agendamento": "BOOKING",
    "login": "LOGIN",
    "sign-in": "LOGIN",
}
FORBIDDEN_TAGS = {"base", "object", "embed", "applet"}
FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("HTML_SERVICE_WORKER_FORBIDDEN", re.compile(r"navigator\s*\.\s*serviceWorker", re.I)),
    ("HTML_COOKIE_ACCESS_FORBIDDEN", re.compile(r"document\s*\.\s*cookie", re.I)),
    (
        "HTML_PARENT_ACCESS_FORBIDDEN",
        re.compile(
            r"(?:window\s*\.\s*(?:parent|top|opener)|(?:parent|top|opener)\s*\.\s*(?:document|location|postMessage))",
            re.I,
        ),
    ),
    ("HTML_JAVASCRIPT_URL_FORBIDDEN", re.compile(r"javascript\s*:", re.I)),
)


def _issue(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


class _HtmlInspection(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.has_doctype = False
        self.has_html = False
        self.has_head = False
        self.has_body = False
        self.meta: dict[str, str] = {}
        self.external_scripts: list[str] = []
        self.external_stylesheets: list[str] = []
        self.forbidden_tags: list[str] = []
        self.event_handler_attributes: list[str] = []

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower() == "doctype html":
            self.has_doctype = True

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        lowered = tag.lower()
        if lowered == "html":
            self.has_html = True
        elif lowered == "head":
            self.has_head = True
        elif lowered == "body":
            self.has_body = True
        if lowered in FORBIDDEN_TAGS:
            self.forbidden_tags.append(lowered)

        attributes = {str(key).lower(): str(value or "") for key, value in attrs}
        for key in attributes:
            if key.startswith("on"):
                self.event_handler_attributes.append(key)

        if lowered == "meta":
            name = attributes.get("name", "").strip().lower()
            if name:
                self.meta[name] = attributes.get("content", "").strip()
        elif lowered == "script" and attributes.get("src"):
            self.external_scripts.append(attributes["src"])
        elif lowered == "link":
            rel = attributes.get("rel", "").lower().split()
            href = attributes.get("href", "").strip()
            if "stylesheet" in rel and href:
                self.external_stylesheets.append(href)


class HtmlTemplateContract:
    """Contrato HTML para Landing, Agenda Pública e Login visual."""

    @staticmethod
    def is_html_content(content: Any) -> bool:
        return (
            isinstance(content, dict)
            and str(content.get("render_mode") or "").upper() == "HTML"
            and isinstance(content.get("html_document"), str)
        )

    @staticmethod
    def descriptor() -> dict[str, Any]:
        return {
            "name": HTML_CONTRACT_NAME,
            "schema": HTML_CONTRACT_SCHEMA,
            "version": HTML_CONTRACT_VERSION,
            "authoring_format": "text/html",
            "max_bytes": HTML_MAX_BYTES,
            "required_meta": [
                "scheduler-pro-template",
                "scheduler-pro-content-version",
                "scheduler-pro-surface",
                "viewport",
            ],
            "surfaces": {
                "landing": "Landing Page, com ou sem agenda pública habilitada.",
                "public-booking": "Página pública de agendamento conectada ao motor do Scheduler Pro.",
                "login": "Página visual de Login conectada à autenticação real do Scheduler Pro.",
            },
            "runtime": {
                "sandboxed": True,
                "same_origin_access": False,
                "public_api_bridge": [
                    "GET /api/v1/public/booking",
                    "GET /api/v1/public/booking/availability",
                    "POST /api/v1/public/booking",
                ],
                "inline_css": True,
                "inline_javascript": True,
                "base64_assets": True,
                "external_script_src": False,
            },
        }

    @classmethod
    def validate_html(
        cls,
        html_document: Any,
        *,
        expected_surface: str | None = None,
    ) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        if not isinstance(html_document, str):
            return {
                "valid": False,
                "schema": HTML_CONTRACT_SCHEMA,
                "errors": [
                    _issue(
                        "html",
                        "HTML_STRING_REQUIRED",
                        "Envie um documento HTML completo.",
                    )
                ],
                "warnings": [],
            }

        size = len(html_document.encode("utf-8"))
        if not html_document.strip():
            errors.append(_issue("html", "HTML_EMPTY", "O documento HTML está vazio."))
        if size > HTML_MAX_BYTES:
            errors.append(
                _issue(
                    "html",
                    "HTML_TOO_LARGE",
                    f"O HTML excede o limite de {HTML_MAX_BYTES // (1024 * 1024)} MB.",
                )
            )

        parser = _HtmlInspection()
        try:
            parser.feed(html_document)
            parser.close()
        except Exception as exc:
            errors.append(
                _issue(
                    "html",
                    "HTML_PARSE_FAILED",
                    f"Não foi possível analisar o HTML: {exc.__class__.__name__}.",
                )
            )

        if not parser.has_doctype:
            errors.append(_issue("doctype", "HTML_DOCTYPE_REQUIRED", "Use <!doctype html>."))
        if not parser.has_html or not parser.has_head or not parser.has_body:
            errors.append(
                _issue(
                    "document",
                    "HTML_DOCUMENT_STRUCTURE_REQUIRED",
                    "O arquivo precisa conter html, head e body.",
                )
            )

        viewport = parser.meta.get("viewport", "")
        if "width=device-width" not in viewport.replace(" ", "").lower():
            errors.append(
                _issue(
                    "meta.viewport",
                    "HTML_VIEWPORT_REQUIRED",
                    "Defina viewport responsivo com width=device-width.",
                )
            )

        key = parser.meta.get("scheduler-pro-template", "").strip().lower()
        if len(key) < 2 or not TEMPLATE_KEY_RE.fullmatch(key):
            errors.append(
                _issue(
                    "meta.scheduler-pro-template",
                    "HTML_TEMPLATE_KEY_INVALID",
                    "Informe scheduler-pro-template usando letras minúsculas, números e hífen.",
                )
            )

        raw_version = parser.meta.get("scheduler-pro-content-version", "").strip()
        try:
            parsed_version = float(raw_version)
            version: int | float = int(parsed_version) if parsed_version.is_integer() else parsed_version
        except (TypeError, ValueError):
            version = 0

        declared_surface = parser.meta.get("scheduler-pro-surface", "").strip().lower()
        surface = SURFACE_META_TO_INTERNAL.get(declared_surface, "")
        minimum_version = 1 if surface == "LOGIN" else 2
        if version < minimum_version:
            errors.append(
                _issue(
                    "meta.scheduler-pro-content-version",
                    "HTML_CONTENT_VERSION_INVALID",
                    f"Use scheduler-pro-content-version igual ou superior a {minimum_version} para {surface or 'esta superfície'}.",
                )
            )
        if not surface:
            errors.append(
                _issue(
                    "meta.scheduler-pro-surface",
                    "HTML_SURFACE_INVALID",
                    "Use scheduler-pro-surface=landing, public-booking/booking ou login.",
                )
            )
        normalized_expected = str(expected_surface or "").strip().upper()
        if normalized_expected and surface and surface != normalized_expected:
            errors.append(
                _issue(
                    "meta.scheduler-pro-surface",
                    "HTML_SURFACE_MISMATCH",
                    f"O arquivo declara {surface}, mas esta área exige {normalized_expected}.",
                )
            )

        for tag in sorted(set(parser.forbidden_tags)):
            errors.append(
                _issue(
                    f"tag.{tag}",
                    "HTML_TAG_FORBIDDEN",
                    f"A tag <{tag}> não é permitida em modelos HTML.",
                )
            )
        for src in parser.external_scripts:
            errors.append(
                _issue(
                    "script.src",
                    "HTML_EXTERNAL_SCRIPT_FORBIDDEN",
                    f"Scripts externos não são permitidos: {src[:180]}.",
                )
            )
        if parser.event_handler_attributes:
            warnings.append(
                _issue(
                    "attributes",
                    "HTML_INLINE_EVENT_HANDLER_DISCOURAGED",
                    "Prefira addEventListener em scripts internos em vez de atributos on*.",
                )
            )
        if parser.external_stylesheets:
            warnings.append(
                _issue(
                    "link.stylesheet",
                    "HTML_EXTERNAL_STYLESHEET_DEPENDENCY",
                    "O modelo usa folha de estilo externa; para maior previsibilidade prefira CSS incorporado.",
                )
            )

        for code, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(html_document):
                errors.append(
                    _issue(
                        "html",
                        code,
                        "O modelo tenta acessar um recurso de navegador bloqueado pelo isolamento do Scheduler Pro.",
                    )
                )

        lowered = html_document.lower()
        has_direct_booking_api = "/api/v1/public/booking" in lowered
        has_declared_booking_bridge = "data-scheduler-pro-booking" in lowered
        # Experience Contract v2 / Template Runtime SDK v1: o template pode usar
        # o bridge semântico do host sem hardcode de endpoint público.
        has_runtime_booking_bridge = (
            "argwsruntime.booking" in lowered
            or "schedulerpro.booking" in lowered
        )
        has_composed_booking_api = (
            "/api/v1/public" in lowered
            and re.search(r"[\"'`]\/booking(?:\/availability)?(?:\?|[\"'`])", lowered)
            is not None
        )
        if surface == "BOOKING" and not (
            has_direct_booking_api
            or has_declared_booking_bridge
            or has_runtime_booking_bridge
            or has_composed_booking_api
        ):
            errors.append(
                _issue(
                    "html",
                    "HTML_BOOKING_INTEGRATION_REQUIRED",
                    "A Página de Agendamento precisa usar a API pública do Scheduler Pro ou declarar data-scheduler-pro-booking.",
                )
            )
        if surface == "LOGIN":
            has_login_form = "id=\"loginform\"" in lowered or "id='loginform'" in lowered
            has_auth_bridge = (
                "schedulerproauth.login" in lowered
                or "window.schedulerproauth" in lowered and ".login" in lowered
                or "data-scheduler-pro-login" in lowered
                or "data-sp-auth-binding=\"application\"" in lowered
                or "data-sp-auth-binding='application'" in lowered
            )
            if not (has_login_form and has_auth_bridge):
                errors.append(
                    _issue(
                        "html",
                        "HTML_LOGIN_INTEGRATION_REQUIRED",
                        "A página de Login precisa declarar #loginForm e usar a autenticação real via SchedulerProAuth.login.",
                    )
                )

        if surface == "LANDING" and "@media" not in lowered:
            warnings.append(
                _issue(
                    "style",
                    "HTML_RESPONSIVE_STYLE_RECOMMENDED",
                    "Não foi encontrada regra @media; confirme manualmente a responsividade em celular e tablet.",
                )
            )

        return {
            "valid": not errors,
            "schema": HTML_CONTRACT_SCHEMA,
            "template_key": key,
            "content_version": version,
            "declared_surface": declared_surface,
            "surface": surface,
            "bytes": size,
            "errors": errors,
            "warnings": warnings,
        }

    @classmethod
    def ensure_html(
        cls,
        html_document: Any,
        *,
        expected_surface: str | None = None,
    ) -> dict[str, Any]:
        report = cls.validate_html(html_document, expected_surface=expected_surface)
        if not report["valid"]:
            raise APIError(
                "HTML_TEMPLATE_INVALID",
                "O HTML não atende ao padrão de modelos do Scheduler Pro.",
                422,
                details=report,
            )
        return report

    @classmethod
    def wrapper(
        cls,
        html_document: str,
        *,
        expected_surface: str | None = None,
    ) -> dict[str, Any]:
        report = cls.ensure_html(html_document, expected_surface=expected_surface)
        return {
            "render_mode": "HTML",
            "contract": HTML_CONTRACT_SCHEMA,
            "template_key": report["template_key"],
            "surface": report["surface"],
            "content_version": report["content_version"],
            "html_document": html_document,
        }

    @classmethod
    def ensure_wrapper(
        cls,
        content: dict[str, Any],
        *,
        expected_surface: str | None = None,
    ) -> dict[str, Any]:
        if not cls.is_html_content(content):
            raise APIError(
                "HTML_TEMPLATE_WRAPPER_INVALID",
                "Conteúdo HTML inválido.",
                422,
            )
        html_document = str(content["html_document"])
        normalized = cls.wrapper(html_document, expected_surface=expected_surface)
        for key, value in deepcopy(content).items():
            if key not in normalized and key != "html_document":
                normalized[key] = value
        return normalized

    @classmethod
    def validate_family(
        cls,
        *,
        landing_html: str | None = None,
        booking_html: str | None = None,
        login_html: str | None = None,
    ) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        reports: dict[str, dict[str, Any]] = {}
        if not landing_html and not booking_html and not login_html:
            errors.append(_issue("files", "HTML_TEMPLATE_FILE_REQUIRED", "Envie Landing, Agenda Pública ou Login."))
        if landing_html:
            reports["landing"] = cls.validate_html(landing_html, expected_surface="LANDING")
        if booking_html:
            reports["booking"] = cls.validate_html(booking_html, expected_surface="BOOKING")
        if login_html:
            reports["login"] = cls.validate_html(login_html, expected_surface="LOGIN")
        for name, report in reports.items():
            for item in report["errors"]:
                errors.append({**item, "path": f"{name}.{item['path']}"})
            for item in report["warnings"]:
                warnings.append({**item, "path": f"{name}.{item['path']}"})
        keys = {str(report.get("template_key") or "") for report in reports.values() if report.get("template_key")}
        if len(keys) > 1:
            errors.append(_issue("files", "HTML_TEMPLATE_FAMILY_KEY_MISMATCH", "Landing, Agenda Pública e Login precisam usar a mesma chave scheduler-pro-template."))
        return {"valid": not errors, "schema": HTML_CONTRACT_SCHEMA, "template_key": next(iter(keys), ""), "errors": errors, "warnings": warnings, "surfaces": reports}

    @classmethod
    def ensure_family(
        cls,
        *,
        landing_html: str | None = None,
        booking_html: str | None = None,
        login_html: str | None = None,
    ) -> dict[str, Any]:
        report = cls.validate_family(landing_html=landing_html, booking_html=booking_html, login_html=login_html)
        if not report["valid"]:
            raise APIError("HTML_TEMPLATE_FAMILY_INVALID", "A família HTML não atende ao padrão do Scheduler Pro.", 422, details=report)
        return report

    @classmethod
    def validate_pair(
        cls,
        *,
        landing_html: str | None = None,
        booking_html: str | None = None,
    ) -> dict[str, Any]:
        """Compatibilidade 2.3.0: mantém o código de erro histórico do par.

        O contrato 2.3.1 trata LANDING/BOOKING/LOGIN como uma família, porém
        consumidores antigos ainda verificam HTML_TEMPLATE_PAIR_KEY_MISMATCH.
        """
        report = cls.validate_family(
            landing_html=landing_html,
            booking_html=booking_html,
        )
        report["errors"] = [
            {
                **issue,
                "code": (
                    "HTML_TEMPLATE_PAIR_KEY_MISMATCH"
                    if issue.get("code") == "HTML_TEMPLATE_FAMILY_KEY_MISMATCH"
                    else issue.get("code")
                ),
            }
            for issue in report["errors"]
        ]
        return report

    @classmethod
    def ensure_pair(
        cls,
        *,
        landing_html: str | None = None,
        booking_html: str | None = None,
    ) -> dict[str, Any]:
        report = cls.validate_pair(
            landing_html=landing_html,
            booking_html=booking_html,
        )
        if not report["valid"]:
            raise APIError(
                "HTML_TEMPLATE_PAIR_INVALID",
                "A família HTML não atende ao padrão do Scheduler Pro.",
                422,
                details=report,
            )
        return report
