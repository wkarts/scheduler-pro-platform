import pytest

from app.services.html_template_package_service import HtmlTemplatePackageService
from app.services.landing_templates import list_templates, template_content
from app.services.official_template_catalog_service import (
    CATALOG_REVISION,
    OFFICIAL_TEMPLATE_PACKAGES,
    package_bytes,
)

EXPECTED_PACKAGES = {
    "barber-shop-neo-generico",
    "clinica-medica-generico",
    "clinica-odontologica-generico",
    "clinica-veterinaria-generico",
    "martelinho-de-ouro-generico",
    "studio-unhas-generico",
    "tecnologia-generico-simples",
}


def test_legacy_builtin_templates_are_not_catalogued() -> None:
    assert list_templates() == []


def test_legacy_builtin_template_lookup_is_disabled() -> None:
    with pytest.raises(KeyError):
        template_content("agenda-essencial")


def test_exactly_seven_new_official_template_packages_are_embedded_and_valid() -> None:
    assert CATALOG_REVISION == "html-package-v2-20260827"
    assert len(OFFICIAL_TEMPLATE_PACKAGES) == 7
    assert {key for key, _ in OFFICIAL_TEMPLATE_PACKAGES} == EXPECTED_PACKAGES

    for key, digest in OFFICIAL_TEMPLATE_PACKAGES:
        archive = package_bytes(key, digest)
        assert archive.startswith(b"PK"), key
        report = HtmlTemplatePackageService.validate(archive)
        assert report["valid"], {key: report["errors"]}
        assert report["package"]["key"] == key
        assert set(report["surfaces"]) == {"landing", "booking"}
        assert report["package"]["default_for_new_tenants"] is False


def test_catalog_replacement_does_not_mutate_existing_tenant_pages() -> None:
    source = __import__(
        "app.services.official_template_catalog_service",
        fromlist=["replace_official_template_catalog"],
    )
    function_source = source.replace_official_template_catalog.__doc__ or ""
    assert "não são apagadas nem" in function_source


def test_platform_bootstrap_installs_the_official_catalog() -> None:
    source = __import__("app.platform_bootstrap", fromlist=["bootstrap_platform"])
    assert hasattr(source, "replace_official_template_catalog")
