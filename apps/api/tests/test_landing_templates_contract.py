import pytest

from app.services.builtin_template_package_service import (
    BUILTIN_TEMPLATE_PACKAGES,
    RESOURCE_DIR,
)
from app.services.html_template_package_service import HtmlTemplatePackageService
from app.services.landing_templates import list_templates, template_content


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


def test_exactly_seven_new_template_packages_are_embedded_and_valid() -> None:
    assert len(BUILTIN_TEMPLATE_PACKAGES) == 7
    keys: set[str] = set()
    for filename in BUILTIN_TEMPLATE_PACKAGES:
        path = RESOURCE_DIR / filename
        assert path.is_file(), filename
        report = HtmlTemplatePackageService.validate(path.read_bytes())
        assert report["valid"], {filename: report["errors"]}
        assert set(report["surfaces"]) == {"landing", "booking"}
        assert report["package"]["scope"] == "INTERNAL"
        assert report["package"]["default_for_new_tenants"] is False
        keys.add(str(report["package"]["key"]))
    assert keys == EXPECTED_PACKAGES
