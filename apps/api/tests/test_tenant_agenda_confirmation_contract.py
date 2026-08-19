from pathlib import Path

import pytest

from app.services.appointment_confirmation_service import AppointmentConfirmationService
from app.services.link_shortener import LinkShortener


def test_confirmation_token_hash_is_stable_and_not_plaintext() -> None:
    token = "customer-confirmation-token"
    hashed = AppointmentConfirmationService._token_hash(token)

    assert hashed != token
    assert len(hashed) == 64
    assert hashed == AppointmentConfirmationService._token_hash(token)


@pytest.mark.asyncio
async def test_shortener_is_optional_and_fails_open() -> None:
    engine = LinkShortener()
    url = "https://tenant.scheduler.argws.com.br/a/token"

    disabled = await engine.shorten(url, enabled=False, provider="none")
    assert disabled.url == url
    assert disabled.shortened is False
    assert disabled.provider == "none"

    future_provider = await engine.shorten(
        url,
        enabled=True,
        provider="future-paid-provider",
        config={"configured": True},
    )
    assert future_provider.url == url
    assert future_provider.shortened is False
    assert future_provider.metadata["reason"] == "provider_not_implemented"


def test_official_provisioning_disables_capabilities_for_new_tenants() -> None:
    source = Path("app/services/provisioning.py").read_text(encoding="utf-8")

    assert "update tenant_capabilities" in source
    assert "set enabled=false" in source
    assert "Control Plane" in source


def test_tenant_confirmation_migration_and_public_route_exist() -> None:
    migration = Path(
        "migrations/alembic_tenant/versions/0006_appointment_confirmation.py"
    ).read_text(encoding="utf-8")
    public_route = Path("app/api/public_appointment_actions.py").read_text(
        encoding="utf-8"
    )
    proxy = Path("../../infrastructure/docker/proxy/default.conf").resolve().read_text(
        encoding="utf-8"
    )

    assert 'revision = "tenant_0006_appointment_confirmation"' in migration
    assert "appointment_confirmation_requests" in migration
    assert 'prefix="/a"' in public_route
    assert "location ^~ /a/" in proxy


def test_tenant_frontend_is_capability_aware_and_agenda_first() -> None:
    source = Path("../../apps/web/src/TenantConsole.vue").resolve().read_text(
        encoding="utf-8"
    )

    assert "/settings/capabilities" in source
    assert "visibleNavItems" in source
    assert "/appointments/quick" in source
    assert "/appointment-confirmations/" in source
    assert "confirmation_deadline_minutes" in source
    assert "tenant_notification_whatsapp" in source
    assert "startTenantRealtime" in source
    assert "enablePushNotifications" in source
