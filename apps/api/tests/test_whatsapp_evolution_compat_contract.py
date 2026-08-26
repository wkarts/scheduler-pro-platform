from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (API_ROOT / relative).read_text(encoding="utf-8")


def test_evolution_remains_the_real_provider() -> None:
    source = _source("app/services/whatsapp_provider.py")
    assert "class EvolutionWhatsAppProvider" in source
    assert "return EvolutionWhatsAppProvider(instance_name)" in source
    assert '"/instance/connect/{self.instance}"' in source
    assert '"/instance/connectionState/{self.instance}"' in source
    assert '"/instance/logout/{self.instance}"' in source


def test_pairing_uses_financial_compatible_number_contract_with_safe_fallback() -> None:
    source = _source("app/services/whatsapp_provider.py")
    assert 'params={"number": normalized}' in source
    assert '"pairingCode": "true"' in source
    assert '"phoneNumber": normalized' in source


def test_send_text_preserves_proven_scheduler_payload_and_only_falls_back_on_schema_rejection() -> None:
    source = _source("app/services/whatsapp_provider.py")
    assert '{"number": to, "textMessage": {"text": message}}' in source
    assert '{"number": to, "text": message}' in source
    assert "if not self._schema_rejection(exc):" in source


def test_legacy_qr_and_status_contract_are_kept_for_existing_tenant_console() -> None:
    source = _source("app/api/v1/routes/whatsapp.py")
    assert '@router.post("/connect")' in source
    assert '@router.get("/status/legacy")' in source
    assert '"status": "CONNECTING"' in source
    assert '"instance_name": instance_name' in source
    assert '"qr": qr' in source
    assert "await provider.connect_instance()" in source
    assert "await provider.connection_status()" in source


def test_automatic_whatsapp_notifications_use_the_same_phone_normalization() -> None:
    source = _source("app/services/notification_dispatcher.py")
    assert "PhoneNormalizationService" in source
    assert "PhoneNormalizationService.from_session(self.session)" in source
    assert "normalized_recipient = phone_service.normalize" in source
    assert "whatsapp_provider.send_text(normalized_recipient, message)" in source
