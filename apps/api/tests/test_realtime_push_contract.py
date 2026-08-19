import re
from pathlib import Path

from app.services.link_shortener import LinkShortener
from app.services.realtime_service import _EVENT_MESSAGES


API_ROOT = Path(__file__).resolve().parents[1]
APPS_ROOT = API_ROOT.parent


def _revision_id(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    match = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    assert match is not None, f"revision ausente em {path.name}"
    return match.group(1)


def test_confirmation_migration_contains_realtime_and_push_tables() -> None:
    migration = (
        API_ROOT
        / "migrations"
        / "alembic_tenant"
        / "versions"
        / "0006_appointment_confirmation.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "tenant_0006_appointment_confirmation"' in migration
    assert "alter column version_num type varchar(128)" in migration.lower()
    assert "appointment_confirmation_requests" in migration
    assert "tenant_realtime_events" in migration
    assert "web_push_vapid_keys" in migration
    assert "web_push_subscriptions" in migration
    assert "tenant_confirmation_confirmed" in migration
    assert "tenant_confirmation_cancelled" in migration
    assert "tenant_confirmation_expired" in migration


def test_alembic_revision_capacity_covers_all_tenant_revisions() -> None:
    """Evita repetir o bootstrap quebrado por VARCHAR(32) em alembic_version."""

    versions = API_ROOT / "migrations" / "alembic_tenant" / "versions"
    revision_ids = [_revision_id(path) for path in sorted(versions.glob("*.py"))]
    assert revision_ids
    assert max(map(len, revision_ids)) <= 128

    long_revisions = [revision for revision in revision_ids if len(revision) > 32]
    if long_revisions:
        migration_0006 = (versions / "0006_appointment_confirmation.py").read_text(
            encoding="utf-8"
        )
        assert "alter column version_num type varchar(128)" in migration_0006.lower()


def test_vapid_private_reference_is_not_stored_in_public_tenant_settings() -> None:
    realtime = (API_ROOT / "app" / "services" / "realtime_service.py").read_text(
        encoding="utf-8"
    )

    assert "web_push_vapid_keys" in realtime
    assert "private_key_ref" in realtime
    assert "web_push_vapid_private_key_ref" not in realtime
    assert "pg_advisory_xact_lock" in realtime


def test_realtime_event_catalog_covers_customer_and_operator_flow() -> None:
    expected = {
        "appointment.created",
        "appointment.confirmed",
        "appointment.customer_confirmed",
        "appointment.cancelled",
        "appointment.customer_cancelled",
        "appointment.rescheduled",
        "appointment.confirmation_expired",
        "appointment.checked_in",
        "appointment.in_progress",
        "appointment.completed",
        "appointment.no_show",
    }
    assert expected.issubset(_EVENT_MESSAGES)


def test_celery_beat_contains_confirmation_expiry_and_push_route() -> None:
    celery = (API_ROOT / "app" / "workers" / "celery_app.py").read_text(
        encoding="utf-8"
    )

    assert "dispatch_realtime_push" in celery
    assert "expire_all_confirmation_requests" in celery
    assert "confirmation-expiry-sweep-every-minute" in celery


def test_tenant_frontend_respects_capabilities_and_uses_quick_agenda() -> None:
    component = (APPS_ROOT / "web" / "src" / "TenantConsole.vue").read_text(
        encoding="utf-8"
    )

    assert "visibleNavItems" in component
    assert "enabledCapabilities" in component
    assert "'/settings/capabilities'" in component
    assert "'/appointments/quick'" in component
    assert "copyConfirmationLink" in component
    assert "startTenantRealtime" in component
    assert "enablePushNotifications" in component


def test_service_worker_handles_push_and_does_not_cache_live_api() -> None:
    service_worker = (APPS_ROOT / "web" / "public" / "sw.js").read_text(
        encoding="utf-8"
    )

    assert "addEventListener('push'" in service_worker
    assert "showNotification" in service_worker
    assert "notificationclick" in service_worker
    assert "url.pathname.startsWith('/api/')" in service_worker
    assert "url.pathname.startsWith('/a/')" in service_worker


def test_link_shortener_remains_optional_and_external_provider_is_not_enabled() -> None:
    assert LinkShortener.SUPPORTED_PROVIDERS == {"none"}
