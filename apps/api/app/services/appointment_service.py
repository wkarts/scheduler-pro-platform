from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AppointmentStatus
from app.core.errors import APIError
from app.db.models_tenant import Appointment


class AppointmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: dict[str, Any]) -> Appointment:
        appointment = Appointment(
            **payload,
            status=AppointmentStatus.awaiting_confirmation.value,
        )
        lock_key = (
            f"appointment:{payload['professional_id']}:"
            f"{payload['starts_at'].isoformat()}:{payload['ends_at'].isoformat()}"
        )
        try:
            async with self.session.begin():
                await self.session.execute(
                    text("select pg_advisory_xact_lock(hashtext(:lock_key))"),
                    {"lock_key": lock_key},
                )
                self.session.add(appointment)
                await self.session.flush()
            return appointment
        except IntegrityError as exc:
            await self.session.rollback()
            raise APIError(
                "APPOINTMENT_SLOT_UNAVAILABLE",
                "Horário não disponível.",
                409,
            ) from exc
