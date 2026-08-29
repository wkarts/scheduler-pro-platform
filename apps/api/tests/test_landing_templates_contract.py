from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.services.builtin_template_package_service import (
    DEFAULT_TEMPLATE_KEY,
    OFFICIAL_TEMPLATE_KEYS,
    builtin_template_archive,
)
from app.services.html_template_package_service import HtmlTemplatePackageService
from app.services.landing_templates import list_templates, template_content


def _html(surface: str) -> str:
    declared = {
        "LANDING": "landing",
        "BOOKING": "public-booking",
        "LOGIN": "login",
    }[surface]
    booking_marker = " data-scheduler-pro-booking" if surface == "BOOKING" else ""
    login_body = (
        '<form id="loginForm" data-sp-auth-binding="application"></form>'
        '<script>window.SchedulerProAuth.login("a@b.com","secret")</script>'
        if surface == "LOGIN"
        else "<main>Scheduler Pro</main>"
    )
    version = 1 if surface == "LOGIN" else 2
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="scheduler-pro-template" content="modelo-teste">
  <meta name="scheduler-pro-content-version" content="{version}">
  <meta name="scheduler-pro-surface" content="{declared}">
  <title>Modelo de teste</title>
  <style>body{{margin:0}} @media(max-width:700px){{body{{padding:8px}}}}</style>
</head>
<body{booking_marker}>{login_body}</body>
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
                "login": {
                    "surface": "LOGIN",
                    "renderer": "HTML",
                    "version": 1,
                    "route": "/login",
                    "entry": "login.html",
                },
            },
        },
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as zipped:
        zipped.writestr("template.json", json.dumps(manifest, ensure_ascii=False))
        zipped.writestr("landing.html", _html("LANDING"))
        zipped.writestr("agendamento.html", _html("BOOKING"))
        zipped.writestr("login.html", _html("LOGIN"))
    return buffer.getvalue()


def test_legacy_builtin_templates_are_not_catalogued() -> None:
    assert list_templates() == []


def test_legacy_builtin_template_lookup_is_disabled() -> None:
    with pytest.raises(KeyError):
        template_content("agenda-essencial")


def test_template_package_contract_validates_three_real_pages() -> None:
    archive = _package()
    assert archive.startswith(b"PK")
    report = HtmlTemplatePackageService.validate(archive)
    assert report["valid"], report["errors"]
    assert report["package"]["key"] == "modelo-teste"
    assert set(report["surfaces"]) == {"landing", "booking", "login"}
    assert report["surfaces"]["login"]["surface"] == "LOGIN"


EXPECTED_OFFICIAL_KEYS = {
    "scheduler-pro-padrao-generico",
    "barber-shop-neo-generico",
    "clinica-medica-generico",
    "clinica-odontologica-generico",
    "clinica-veterinaria-generico",
    "martelinho-de-ouro-generico",
    "studio-unhas-generico",
    "tecnologia-generico-simples",
}


def test_eight_official_page_families_are_real_zip_packages() -> None:
    assert set(OFFICIAL_TEMPLATE_KEYS) == EXPECTED_OFFICIAL_KEYS
    assert len(OFFICIAL_TEMPLATE_KEYS) == 8
    assert DEFAULT_TEMPLATE_KEY == "scheduler-pro-padrao-generico"
    for key in OFFICIAL_TEMPLATE_KEYS:
        archive = builtin_template_archive(key)
        assert archive.startswith(b"PK")
        report = HtmlTemplatePackageService.validate(archive)
        assert report["valid"], {key: report["errors"]}
        assert report["package"]["key"] == key
        assert report["schema"] == "argws-experience-package/v2"
        assert set(report["surfaces"]) == {"landing", "booking"}
        assert report["surfaces"]["landing"]["surface"] == "LANDING"
        assert report["surfaces"]["booking"]["surface"] == "BOOKING"


def test_generic_template_is_the_platform_fallback() -> None:
    report = HtmlTemplatePackageService.ensure(
        builtin_template_archive(DEFAULT_TEMPLATE_KEY)
    )
    assert report["package"]["scope"] == "PLATFORM_DEFAULT"
    assert report["package"]["default_for_new_tenants"] is True


def test_platform_bootstrap_installs_official_page_families() -> None:
    source = __import__("app.platform_bootstrap", fromlist=["bootstrap_platform"])
    assert hasattr(source, "bootstrap_template_library")
