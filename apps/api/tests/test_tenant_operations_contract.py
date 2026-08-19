from datetime import datetime
from zoneinfo import ZoneInfo

from app.api.v1.routes.appointment_operations import (
    RecurringAppointmentCreate,
    _candidate_starts,
)
from app.core.tenant_context import TenantContext
from app.services.tenant_mail_service import SMTP_DELIVERY_MODE_KEY


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
