from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

from app.services.html_template_package_service import (
    PACKAGE_SCHEMA,
    HtmlTemplatePackageService,
)


LANDING_HTML = """<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="scheduler-pro-template" content="modelo-teste">
<meta name="scheduler-pro-content-version" content="2">
<meta name="scheduler-pro-surface" content="landing">
<style>@media(max-width:640px){body{padding:10px}}</style>
</head><body><main><h1>Landing</h1><a href="/agendar">Agendar</a></main></body></html>"""

BOOKING_HTML = """<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="scheduler-pro-template" content="modelo-teste">
<meta name="scheduler-pro-content-version" content="2">
<meta name="scheduler-pro-surface" content="public-booking">
<style>@media(max-width:640px){main{padding:10px}}</style>
</head><body><main data-scheduler-pro-booking><h1>Agendamento</h1></main>
<script>fetch('/api/v1/public/booking')</script></body></html>"""


def manifest(*, key: str = "modelo-teste", schema: str = PACKAGE_SCHEMA) -> dict[str, object]:
    return {
        "schema": schema,
        "package": {
            "key": key,
            "name": "Modelo Teste",
            "description": "Modelo de validação do pacote.",
            "segment": "generico",
            "scope": "INTERNAL",
            "default_for_new_tenants": False,
            "surfaces": {
                "landing": {
                    "version": 2,
                    "surface": "LANDING",
                    "renderer": "HTML",
                    "entry": "landing.html",
                    "route": "/pagina",
                },
                "booking": {
                    "version": 2,
                    "surface": "BOOKING",
                    "renderer": "HTML",
                    "entry": "agendamento.html",
                    "route": "/agendar",
                },
            },
        },
    }


def package_bytes(
    *,
    manifest_value: dict[str, object] | None = None,
    landing: str = LANDING_HTML,
    booking: str = BOOKING_HTML,
    extra: dict[str, str] | None = None,
) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as zipped:
        zipped.writestr(
            "template.json",
            json.dumps(manifest_value or manifest(), ensure_ascii=False),
        )
        zipped.writestr("landing.html", landing)
        zipped.writestr("agendamento.html", booking)
        for name, value in (extra or {}).items():
            zipped.writestr(name, value)
    return output.getvalue()


def test_valid_template_package_preserves_landing_and_booking_html() -> None:
    parsed = HtmlTemplatePackageService.ensure(package_bytes())
    assert parsed["valid"] is True
    assert parsed["package"]["key"] == "modelo-teste"
    assert parsed["surfaces"]["landing"]["entry"] == "landing.html"
    assert parsed["surfaces"]["booking"]["entry"] == "agendamento.html"
    assert parsed["documents"]["LANDING"] == LANDING_HTML
    assert parsed["documents"]["BOOKING"] == BOOKING_HTML


def test_template_package_rejects_path_traversal() -> None:
    report = HtmlTemplatePackageService.validate(
        package_bytes(extra={"../fora.html": "nao permitido"})
    )
    assert report["valid"] is False
    assert any(item["code"] == "PACKAGE_PATH_UNSAFE" for item in report["errors"])


def test_template_package_rejects_manifest_html_key_mismatch() -> None:
    report = HtmlTemplatePackageService.validate(
        package_bytes(manifest_value=manifest(key="outra-chave"))
    )
    assert report["valid"] is False
    assert any(
        item["code"] == "PACKAGE_HTML_KEY_MISMATCH"
        for item in report["errors"]
    )


def test_template_package_rejects_wrong_schema() -> None:
    report = HtmlTemplatePackageService.validate(
        package_bytes(manifest_value=manifest(schema="outro-schema/v1"))
    )
    assert report["valid"] is False
    assert any(item["code"] == "PACKAGE_SCHEMA_INVALID" for item in report["errors"])


def test_template_package_requires_canonical_booking_route() -> None:
    value = manifest()
    value["package"]["surfaces"]["booking"]["route"] = "/outra-rota"  # type: ignore[index]
    report = HtmlTemplatePackageService.validate(package_bytes(manifest_value=value))
    assert report["valid"] is False
    assert any(item["code"] == "PACKAGE_ROUTE_INVALID" for item in report["errors"])
