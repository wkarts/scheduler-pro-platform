from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.services.html_template_package_service import HtmlTemplatePackageService
from app.services.landing_templates import list_templates, template_content


def _html(surface: str) -> str:
    declared = "landing" if surface == "LANDING" else "public-booking"
    booking_marker = " data-scheduler-pro-booking" if surface == "BOOKING" else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="scheduler-pro-template" content="modelo-teste">
  <meta name="scheduler-pro-content-version" content="2">
  <meta name="scheduler-pro-surface" content="{declared}">
  <title>Modelo de teste</title>
  <style>body{{margin:0}} @media(max-width:700px){{body{{padding:8px}}}}</style>
</head>
<body{booking_marker}><main>Scheduler Pro</main></body>
</html>"""


def _package() -> bytes:
    manifest = {
        "schema": "scheduler-pro-template-package/v1",
        "package": {
            "key": "modelo-teste",
            "name": "Modelo de teste",
            "segment": "genérico",
            "scope": "INTERNAL",
            "default_for_new_tenants": False,
            "surfaces": {
                "landing": {
                    "surface": "LANDING",
                    "renderer": "HTML",
                    "version": 2,
                    "route": "/pagina",
                    "entry": "landing.html",
                },
                "booking": {
                    "surface": "BOOKING",
                    "renderer": "HTML",
                    "version": 2,
                    "route": "/agendar",
                    "entry": "agendamento.html",
                },
            },
        },
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as zipped:
        zipped.writestr("template.json", json.dumps(manifest, ensure_ascii=False))
        zipped.writestr("landing.html", _html("LANDING"))
        zipped.writestr("agendamento.html", _html("BOOKING"))
    return buffer.getvalue()


def test_legacy_builtin_templates_are_not_catalogued() -> None:
    assert list_templates() == []


def test_legacy_builtin_template_lookup_is_disabled() -> None:
    with pytest.raises(KeyError):
        template_content("agenda-essencial")


def test_template_package_contract_validates_real_zip_bytes() -> None:
    archive = _package()
    assert archive.startswith(b"PK")
    report = HtmlTemplatePackageService.validate(archive)
    assert report["valid"], report["errors"]
    assert report["package"]["key"] == "modelo-teste"
    assert report["package"]["scope"] == "INTERNAL"
    assert report["package"]["default_for_new_tenants"] is False
    assert set(report["surfaces"]) == {"landing", "booking"}


def test_template_library_does_not_require_embedded_base64_archives() -> None:
    # A biblioteca global é alimentada pela Central de Importação do Control Plane.
    # Templates autorais são ZIPs reais enviados pelo usuário, nunca .zip.b64
    # acoplados ao código-fonte ou ao bootstrap da plataforma.
    source = __import__("app.platform_bootstrap", fromlist=["bootstrap_platform"])
    assert not hasattr(source, "bootstrap_template_library")
