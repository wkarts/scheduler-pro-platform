from typing import Any

import pytest

from app.api.v1.routes import whatsapp as whatsapp_routes
from app.services.phone_normalization import PhoneNormalizationService, PhonePolicy
from app.services.whatsapp_provider import EvolutionWhatsAppProvider


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class _FakeProvider:
    async def connect_instance(self) -> dict[str, Any]:
        return {
            "instance": "scheduler-pro-cliente",
            "connection": {
                "qrcode": {
                    "base64": "A" * 1024,
                    "count": 1,
                }
            },
        }


@pytest.mark.asyncio
async def test_legacy_scheduler_connect_contract_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _FakeSession()
    stored: dict[str, Any] = {}

    async def fake_tenant_provider(*_args: object) -> tuple[str, _FakeProvider]:
        return "scheduler-pro-cliente", _FakeProvider()

    async def fake_stored_settings(*_args: object) -> dict[str, Any]:
        return stored

    async def fake_persist(*_args: object, **kwargs: Any) -> None:
        stored["db_status"] = kwargs["status"]

    monkeypatch.setattr(whatsapp_routes, "_tenant_provider", fake_tenant_provider)
    monkeypatch.setattr(whatsapp_routes, "_stored_settings", fake_stored_settings)
    monkeypatch.setattr(whatsapp_routes, "_persist_integration_state", fake_persist)

    result = await whatsapp_routes._connect_response(session, object())  # type: ignore[arg-type]

    assert result["instance_name"] == "scheduler-pro-cliente"
    assert result["status"] == "CONNECTING"
    assert isinstance(result["status"], str)
    assert result["qr"]["base64"] == "data:image/png;base64," + ("A" * 1024)
    assert stored["db_status"] == "CONNECTING"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_evolution_pairing_extends_original_connect_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = EvolutionWhatsAppProvider("scheduler-pro-cliente")
    captured: dict[str, Any] = {}

    async def fake_ensure() -> dict[str, Any]:
        return {"created": False}

    async def fake_request(
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        captured.update(method=method, path=path, payload=payload, params=params)
        return {"pairingCode": "1234-5678"}

    monkeypatch.setattr(provider, "ensure_instance", fake_ensure)
    monkeypatch.setattr(provider, "_request", fake_request)

    result = await provider.connect_pairing("5575988881111")

    assert captured["method"] == "GET"
    assert captured["path"] == "/instance/connect/scheduler-pro-cliente"
    assert captured["params"] == {"number": "5575988881111"}
    assert result["connection"]["pairingCode"] == "1234-5678"


def test_missing_brazilian_prefixes_are_normalized_before_evolution() -> None:
    service = PhoneNormalizationService(
        PhonePolicy(country="BR", country_code="55", area_code="75", add_ninth_digit=True)
    )

    expected = "5575988881111"
    assert service.normalize("88881111", required=True) == expected
    assert service.normalize("988881111", required=True) == expected
    assert service.normalize("7588881111", required=True) == expected
    assert service.normalize("+55 (75) 98888-1111", required=True) == expected
    assert service.normalize(expected, required=True) == expected


def test_public_product_name_does_not_expose_internal_provider() -> None:
    assert whatsapp_routes.PUBLIC_PRODUCT_NAME == "ARGWS Whatsapp API"
