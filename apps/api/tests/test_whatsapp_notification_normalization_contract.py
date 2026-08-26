from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]


def test_notification_dispatcher_normalizes_whatsapp_recipient_before_provider() -> None:
    source = (API_ROOT / "app/services/notification_dispatcher.py").read_text(
        encoding="utf-8"
    )

    assert "from app.services.phone_normalization import PhoneNormalizationService" in source
    assert "PhoneNormalizationService.from_session(self.session)" in source
    assert "normalized_recipient = phone_service.normalize" in source
    assert "required=True" in source
    assert "whatsapp_provider.send_text(normalized_recipient, message)" in source


def test_notification_dispatcher_keeps_existing_evolution_provider_factory() -> None:
    source = (API_ROOT / "app/services/notification_dispatcher.py").read_text(
        encoding="utf-8"
    )

    assert "WhatsAppProviderFactory.make(instance_name)" in source
    assert "notification_jobs" in source
    assert "status='PENDING'" in source
