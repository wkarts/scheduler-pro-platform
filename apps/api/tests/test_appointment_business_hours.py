import asyncio
from datetime import UTC, datetime, time
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.appointment_service import AppointmentService


class _BusinessHoursSession:
    def __init__(self) -> None:
        self.info: dict[str, Any] = {"tenant_timezone": "America/Bahia"}
        self.last_params: dict[str, Any] = {}

    async def scalar(self, statement: object, params: dict[str, Any] | None = None) -> object:
        sql = str(statement)
        if "count(*) from business_hours" in sql:
            return 1
        if "select exists(" in sql and "business_hours" in sql:
            self.last_params = dict(params or {})
            return True
        raise AssertionError(f"SQL inesperado no teste: {sql}")


def test_business_hours_uses_native_time_parameters_for_asyncpg() -> None:
    fake = _BusinessHoursSession()
    service = AppointmentService(cast(AsyncSession, fake))

    result = asyncio.run(
        service._is_inside_business_hours(
            "11111111-1111-1111-1111-111111111111",
            datetime(2026, 8, 19, 15, 30, tzinfo=UTC),
            datetime(2026, 8, 19, 16, 0, tzinfo=UTC),
        )
    )

    assert result is True
    assert isinstance(fake.last_params["start_time"], time)
    assert isinstance(fake.last_params["end_time"], time)
    assert fake.last_params["start_time"].tzinfo is None
    assert fake.last_params["end_time"].tzinfo is None
