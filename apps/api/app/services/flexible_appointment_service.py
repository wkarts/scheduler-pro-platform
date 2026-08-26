from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import text

from app.core.errors import APIError
from app.services.appointment_service import AppointmentService
from app.services.booking_parameters_service import BookingParametersService
from app.services.phone_normalization import PhoneNormalizationService


class FlexibleAppointmentService(AppointmentService):
    """Extensão incremental do motor legado para modelos de negócio flexíveis.

    O AppointmentService permanece intacto para compatibilidade. Novos fluxos de
    criação usam esta classe e só relaxam uma regra quando o tenant a desativou.
    Defaults continuam equivalentes ao comportamento histórico.
    """

    async def booking_parameters(self) -> dict[str, Any]:
        return await BookingParametersService(self.session).get()

    async def _validate_customer(self, customer_id: str) -> None:
        params = await self.booking_parameters()
        row = (
            await self.session.execute(
                text(
                    """
                    select id::text, name, phone, phone_normalized
                    from customers
                    where id=cast(:id as uuid)
                    limit 1
                    """
                ),
                {"id": customer_id},
            )
        ).mappings().first()
        if row is None:
            raise APIError("CUSTOMER_NOT_FOUND", "Cliente não encontrado.", 404)
        if len(str(row["name"] or "").strip()) < 2:
            raise APIError(
                "APPOINTMENT_CUSTOMER_NAME_REQUIRED",
                "Informe o nome do cliente.",
                422,
            )

        phone = str(row["phone_normalized"] or row["phone"] or "").strip()
        phone_mode = str(params.get("phone_mode") or "REQUIRED").upper()
        if not phone:
            if phone_mode == "REQUIRED":
                raise APIError(
                    "APPOINTMENT_CUSTOMER_PHONE_REQUIRED",
                    "Informe o telefone/WhatsApp do cliente.",
                    422,
                )
            return
        normalizer = await PhoneNormalizationService.from_session(self.session)
        await normalizer.normalize_customer_phone(
            self.session,
            customer_id=customer_id,
            value=phone,
        )

    async def _ensure_slot_available(
        self,
        professional_id: str,
        starts_at: datetime,
        ends_at: datetime,
        *,
        source: str = "internal",
        ignore_appointment_id: str | None = None,
    ) -> None:
        starts_at = self._aware(starts_at)
        ends_at = self._aware(ends_at)
        if ends_at <= starts_at:
            raise APIError(
                "APPOINTMENT_INVALID_INTERVAL",
                "Fim deve ser posterior ao início.",
                422,
            )

        params = await self.booking_parameters()
        rules = params.get("rules") if isinstance(params.get("rules"), dict) else {}
        if bool(rules.get("enforce_business_hours", True)):
            if not await self._is_inside_business_hours(professional_id, starts_at, ends_at):
                raise APIError(
                    "APPOINTMENT_OUTSIDE_BUSINESS_HOURS",
                    "Horário fora do expediente.",
                    409,
                )
        if bool(rules.get("enforce_blocked_periods", True)):
            if await self._is_blocked(professional_id, starts_at, ends_at):
                raise APIError("APPOINTMENT_BLOCKED_PERIOD", "Horário bloqueado.", 409)

        simultaneous = (
            params.get("simultaneous")
            if isinstance(params.get("simultaneous"), dict)
            else {}
        )
        public = str(source or "").lower().startswith("public")
        enforce_capacity = bool(
            simultaneous.get("enforce_public" if public else "enforce_internal", True)
        )
        if not enforce_capacity:
            return

        await self._lock_professional_capacity(professional_id)
        occupied = await self._overlap_count(
            professional_id,
            starts_at,
            ends_at,
            ignore_appointment_id=ignore_appointment_id,
        )
        capacity = await self.capacity(source)
        if occupied >= capacity:
            raise APIError(
                "APPOINTMENT_SLOT_UNAVAILABLE",
                "Horário sem capacidade disponível.",
                409,
                {"capacity": capacity, "occupied": occupied},
            )

    async def availability(
        self,
        *,
        day: date,
        professional_id: str,
        service_id: str | None = None,
        slot_minutes: int = 30,
        source: str = "internal",
    ) -> list[dict[str, Any]]:
        params = await self.booking_parameters()
        duration = slot_minutes
        if service_id:
            service_duration = await self.session.scalar(
                text(
                    "select duration_minutes from services "
                    "where id=cast(:id as uuid) and active='true'"
                ),
                {"id": service_id},
            )
            if service_duration is None:
                raise APIError("SERVICE_NOT_FOUND", "Serviço indisponível.", 404)
            duration = int(service_duration)
        elif str(params.get("duration_mode") or "REQUIRED").upper() == "DISABLED":
            duration = int(params.get("default_duration_minutes") or 60)
        elif str(params.get("service_mode") or "REQUIRED").upper() != "REQUIRED":
            duration = int(params.get("default_duration_minutes") or 60)

        rules = params.get("rules") if isinstance(params.get("rules"), dict) else {}
        simultaneous = (
            params.get("simultaneous")
            if isinstance(params.get("simultaneous"), dict)
            else {}
        )
        public = str(source or "").lower().startswith("public")
        enforce_capacity = bool(
            simultaneous.get("enforce_public" if public else "enforce_internal", True)
        )
        enforce_business_hours = bool(rules.get("enforce_business_hours", True))
        enforce_blocked_periods = bool(rules.get("enforce_blocked_periods", True))
        capacity = await self.capacity(source) if enforce_capacity else 10000

        local_day_start = datetime.combine(day, time(hour=8), tzinfo=self.timezone)
        local_day_end = datetime.combine(day, time(hour=18), tzinfo=self.timezone)
        windows: list[tuple[datetime, datetime]] = []
        if enforce_business_hours:
            business_rows = (
                await self.session.execute(
                    text(
                        """
                        select opens_at, closes_at from business_hours
                        where day_of_week=:dow and is_open=true
                          and (
                            professional_id is null
                            or professional_id=cast(:professional_id as uuid)
                          )
                        order by professional_id nulls last
                        """
                    ),
                    {
                        "dow": int(local_day_start.strftime("%w")),
                        "professional_id": professional_id,
                    },
                )
            ).mappings().all()
            for row in business_rows:
                local_start = datetime.combine(day, row["opens_at"], tzinfo=self.timezone)
                local_end = datetime.combine(day, row["closes_at"], tzinfo=self.timezone)
                windows.append((local_start.astimezone(UTC), local_end.astimezone(UTC)))
        if not windows:
            windows.append((local_day_start.astimezone(UTC), local_day_end.astimezone(UTC)))

        slots: list[dict[str, Any]] = []
        step = timedelta(minutes=max(5, slot_minutes))
        service_delta = timedelta(minutes=max(5, duration))
        for start, end_limit in windows:
            cursor = start
            while cursor + service_delta <= end_limit:
                end = cursor + service_delta
                blocked = (
                    await self._is_blocked(professional_id, cursor, end)
                    if enforce_blocked_periods
                    else False
                )
                occupied = (
                    await self._overlap_count(professional_id, cursor, end)
                    if enforce_capacity
                    else 0
                )
                available = not blocked and (not enforce_capacity or occupied < capacity)
                slots.append(
                    {
                        "starts_at": cursor.isoformat(),
                        "ends_at": end.isoformat(),
                        "available": available,
                        "professional_id": professional_id,
                        "service_id": service_id,
                        "capacity": capacity,
                        "occupied": occupied,
                        "remaining_capacity": (
                            max(0, capacity - occupied) if enforce_capacity else None
                        ),
                        "unlimited_capacity": not enforce_capacity,
                    }
                )
                cursor += step
        return slots
