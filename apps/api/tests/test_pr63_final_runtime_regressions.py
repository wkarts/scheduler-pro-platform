from __future__ import annotations

import base64
import io
import json
import zipfile

from app.api.v1.routes.public import _legacy_experience_asset_alias
from app.services.experience_contract_service import ExperienceContractService


def _legacy_archive() -> bytes:
    blob = b"scheduler-pro-pr63-final" * 320
    data_uri = "data:image/png;base64," + base64.b64encode(blob).decode("ascii")
    html_landing = f'<html><body><img src="{data_uri}" data-sp-edit="brand.logo"></body></html>'
    html_booking = f'<html><body><img src="{data_uri}" data-sp-edit="brand.logo"></body></html>'
    manifest = {
        "schema": "scheduler-pro-template-package/v1",
        "package": {"key": "regression-pr63", "name": "Regression PR63"},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("template.json", json.dumps(manifest))
        archive.writestr("landing.html", html_landing)
        archive.writestr("agendamento.html", html_booking)
    return buffer.getvalue()


def test_v1_migration_preserves_both_logical_asset_paths() -> None:
    parsed = ExperienceContractService.parse_archive(_legacy_archive())
    paths = {asset.path for asset in parsed.assets}
    assert len(paths) == 2
    assert any(path.startswith("assets/landing-") for path in paths)
    assert any(path.startswith("assets/booking-") for path in paths)
    assert "landing-" in parsed.landing_html
    assert "booking-" in parsed.booking_html


def test_legacy_asset_alias_is_symmetric() -> None:
    base = "experience/demo/assets/landing-0123456789abcdef.png"
    alternate = _legacy_experience_asset_alias(base)
    assert alternate == "experience/demo/assets/booking-0123456789abcdef.png"
    assert _legacy_experience_asset_alias(alternate) == base
