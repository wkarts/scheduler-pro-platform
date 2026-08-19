from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.api.v1.routes.appointment_operations import (
    RecurringAppointmentCreate,
    _candidate_starts,
)
from app.core.tenant_context import TenantContext
from app.services.tenant_mail_service import SMTP_DELIVERY_MODE_KEY

ROOT = Path(__file__).resolve().parents[3]


def _context() -> TenantContext:
    return TenantContext(
        tenant_id="00000000-0000-0000-0000-000000000001",
        slug="test",
        database="tenant_test",
        database_user="tenant_test_user",
        database_password_ref="secret://env/TEST_PASSWORD",
        storage_bucket="tenant-test",
        hostname="test.scheduler.example",
        timezone="America/Bahia",
    )


def test_recurring_weekly_schedule_respects_weekday_sundays_and_skip_dates() -> None:
    timezone = ZoneInfo("America/Bahia")
    payload = RecurringAppointmentCreate(
        starts_at=datetime(2026, 8, 18, 19, 0, tzinfo=timezone),
        customer_name="Cliente Teste",
        service_name="Atendimento",
        professional_name="Agenda geral",
        duration_minutes=30,
        repeat_every_weeks=1,
        weekdays=[1, 6],
        months_ahead=1,
        max_occurrences=20,
        skip_sundays=True,
        skip_dates=[datetime(2026, 8, 25).date()],
    )
    starts = _candidate_starts(payload, _context())
    local_starts = [value.astimezone(timezone) for value in starts]
    assert local_starts
    assert all(value.weekday() == 1 for value in local_starts)
    assert all(value.hour == 19 and value.minute == 0 for value in local_starts)
    assert datetime(2026, 8, 25).date() not in {value.date() for value in local_starts}


def test_recurring_default_uses_first_appointment_weekday() -> None:
    timezone = ZoneInfo("America/Bahia")
    payload = RecurringAppointmentCreate(
        starts_at=datetime(2026, 8, 19, 8, 30, tzinfo=timezone),
        customer_name="Cliente Teste",
        service_name="Atendimento",
        professional_name="Agenda geral",
        duration_minutes=30,
        repeat_every_weeks=2,
        weekdays=[],
        months_ahead=1,
        max_occurrences=10,
    )
    starts = [value.astimezone(timezone) for value in _candidate_starts(payload, _context())]
    assert starts
    assert all(value.weekday() == 2 for value in starts)
    assert all(value.hour == 8 and value.minute == 30 for value in starts)


def test_smtp_delivery_mode_uses_existing_tenant_settings_without_new_schema_head() -> None:
    assert SMTP_DELIVERY_MODE_KEY == "smtp_delivery_mode"


def test_agenda_customer_picker_is_vue_native_and_not_mutation_injected() -> None:
    agenda = (ROOT / "apps" / "web" / "src" / "TenantAgendaOperations.vue").read_text(encoding="utf-8")
    enhancements = (ROOT / "apps" / "web" / "src" / "tenant-mobile-enhancements.ts").read_text(encoding="utf-8")
    assert "sp-customer-picker-mobile" in agenda
    assert "sp-customer-select-desktop" in agenda
    assert "replaceChildren" not in enhancements
    assert "sp-mobile-option-list" not in enhancements
    assert "enhanceTouchSelects" not in enhancements


def test_tenant_logs_live_inside_administrative_tenant_manager() -> None:
    manager = (ROOT / "apps" / "admin" / "src" / "TenantManagementDrawer.vue").read_text(encoding="utf-8")
    admin_main = (ROOT / "apps" / "admin" / "src" / "main.ts").read_text(encoding="utf-8")
    inspector = (ROOT / "apps" / "admin" / "src" / "TenantLogInspector.vue").read_text(encoding="utf-8")
    assert "Logs e diagnóstico" in manager
    assert "<TenantLogInspector" in manager
    assert "scheduler-pro-tenant-log-inspector" not in admin_main
    assert "/platform/tenant-management/${selected.value}/logs" in inspector
