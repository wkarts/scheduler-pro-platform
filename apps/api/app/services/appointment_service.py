from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AppointmentStatus
from app.core.errors import APIError
from app.db.models_tenant import Appointment
from app.services.notification_service import NotificationService

BUSY_STATUSES = (
    AppointmentStatus.pending.value,
    AppointmentStatus.awaiting_confirmation.value,
    AppointmentStatus.confirmed.value,
    AppointmentStatus.checked_in.value,
    AppointmentStatus.in_progress.value,
)

FINAL_STATUSES = {
    AppointmentStatus.completed.value,
    AppointmentStatus.cancelled.value,
    AppointmentStatus.no_show.value,
}


class AppointmentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        public_base_url: str | None = None,
    ) -> None:
        self.session = session
        self.public_base_url = public_base_url

    async def _require_reference(self, table: str, entity_id: str, code: str) -> None:
        exists = await self.session.scalar(
            text(f"select exists(select 1 from {table} where id=:id::uuid)"),
            {"id": entity_id},
        )
        if not exists:
            raise APIError(code, "Registro relacionado não encontrado.", 404)

    async def _business_hours_configured(self) -> bool:
        total = await self.session.scalar(text("select count(*) from business_hours"))
        return int(total or 0) > 0

    async def _is_inside_business_hours(
        self,
        professional_id: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        if not await self._business_hours_configured():
            return True
        dow = int(starts_at.astimezone(UTC).strftime("%w"))
        result = await self.session.scalar(
            text(
                """
                select exists(
                  select 1 from business_hours
                  where is_open = true
                    and day_of_week = :dow
                    and (professional_id is null or professional_id = :professional_id::uuid)
                    and :start_time::time >= opens_at
                    and :end_time::time <= closes_at
                )
                """
            ),
            {
                "dow": dow,
                "professional_id": professional_id,
                "start_time": starts_at.timetz().replace(tzinfo=None).isoformat(),
                "end_time": ends_at.timetz().replace(tzinfo=None).isoformat(),
            },
        )
        return bool(result)

    async def _is_blocked(
        self,
        professional_id: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        result = await self.session.scalar(
            text(
                """
                select exists(
                  select 1 from blocked_periods
                  where (professional_id is null or professional_id = :professional_id::uuid)
                    and tstzrange(starts_at, ends_at, '[)')
                        && tstzrange(:starts_at, :ends_at, '[)')
                )
                """
            ),
            {
                "professional_id": professional_id,
                "starts_at": starts_at,
                "ends_at": ends_at,
            },
        )
        return bool(result)

    async def _has_overlap(
        self,
        professional_id: str,
        starts_at: datetime,
        ends_at: datetime,
        *,
        ignore_appointment_id: str | None = None,
    ) -> bool:
        base = """
            select exists(
              select 1 from appointments
              where professional_id = :professional_id::uuid
                and status = any(:busy_statuses)
                and tstzrange(starts_at, ends_at, '[)')
                    && tstzrange(:starts_at, :ends_at, '[)')
        """
        params: dict[str, Any] = {
            "professional_id": professional_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "busy_statuses": list(BUSY_STATUSES),
        }
        if ignore_appointment_id:
            base += " and id <> :ignore_appointment_id::uuid"
            params["ignore_appointment_id"] = ignore_appointment_id
        base += ")"
        return bool(await self.session.scalar(text(base), params))

    async def _ensure_slot_available(
        self,
        professional_id: str,
        starts_at: datetime,
        ends_at: datetime,
        *,
        ignore_appointment_id: str | None = None,
    ) -> None:
        if ends_at <= starts_at:
            raise APIError(
                "APPOINTMENT_INVALID_INTERVAL",
                "Fim deve ser posterior ao início.",
                422,
            )
        if not await self._is_inside_business_hours(
            professional_id,
            starts_at,
            ends_at,
        ):
            raise APIError(
                "APPOINTMENT_OUTSIDE_BUSINESS_HOURS",
                "Horário fora do expediente.",
                409,
            )
        if await self._is_blocked(professional_id, starts_at, ends_at):
            raise APIError(
                "APPOINTMENT_BLOCKED_PERIOD",
                "Horário bloqueado.",
                409,
            )
        if await self._has_overlap(
            professional_id,
            starts_at,
            ends_at,
            ignore_appointment_id=ignore_appointment_id,
        ):
            raise APIError(
                "APPOINTMENT_SLOT_UNAVAILABLE",
                "Horário não disponível.",
                409,
            )

    async def create(self, payload: dict[str, Any]) -> Appointment:
        await self._require_reference(
            "customers",
            str(payload["customer_id"]),
            "CUSTOMER_NOT_FOUND",
        )
        await self._require_reference(
            "services",
            str(payload["service_id"]),
            "SERVICE_NOT_FOUND",
        )
        await self._require_reference(
            "professionals",
            str(payload["professional_id"]),
            "PROFESSIONAL_NOT_FOUND",
        )
        lock_key = (
            f"appointment:{payload['professional_id']}:"
            f"{payload['starts_at'].isoformat()}:{payload['ends_at'].isoformat()}"
        )
        appointment = Appointment(
            **payload,
            status=AppointmentStatus.awaiting_confirmation.value,
        )
        try:
            async with self.session.begin():
                await self.session.execute(
                    text("select pg_advisory_xact_lock(hashtext(:lock_key))"),
                    {"lock_key": lock_key},
                )
                await self._ensure_slot_available(
                    str(payload["professional_id"]),
                    payload["starts_at"],
                    payload["ends_at"],
                )
                self.session.add(appointment)
                await self.session.flush()
                await self._add_history(
                    appointment.id,
                    appointment.status,
                    "created",
                )
                await NotificationService(
                    self.session,
                    public_base_url=self.public_base_url,
                ).schedule_for_appointment(
                    str(appointment.id),
                    "appointment_created",
                )
            return appointment
        except IntegrityError as exc:
            await self.session.rollback()
            raise APIError(
                "APPOINTMENT_SLOT_UNAVAILABLE",
                "Horário não disponível.",
                409,
            ) from exc

    async def _add_history(
        self,
        appointment_id: str,
        status: str,
        reason: str | None = None,
    ) -> None:
        await self.session.execute(
            text(
                "insert into appointment_status_history(appointment_id, status, reason) "
                "values(:appointment_id::uuid, :status, :reason)"
            ),
            {
                "appointment_id": appointment_id,
                "status": status,
                "reason": reason,
            },
        )

    @staticmethod
    def _row(row: RowMapping) -> dict[str, Any]:
        return dict(row)

    async def list_appointments(
        self,
        *,
        day: date | None = None,
        professional_id: str | None = None,
        customer_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: dict[str, Any] = {}
        if day:
            clauses.append("a.starts_at >= :day_start and a.starts_at < :day_end")
            params["day_start"] = datetime.combine(day, time.min, tzinfo=UTC)
            params["day_end"] = params["day_start"] + timedelta(days=1)
        if professional_id:
            clauses.append("a.professional_id = :professional_id::uuid")
            params["professional_id"] = professional_id
        if customer_id:
            clauses.append("a.customer_id = :customer_id::uuid")
            params["customer_id"] = customer_id
        if status:
            clauses.append("a.status = :status")
            params["status"] = status
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select a.id::text, a.customer_id::text, a.service_id::text,
                           a.professional_id::text, a.starts_at, a.ends_at,
                           a.status, a.source, a.created_at,
                           c.name as customer_name, c.phone as customer_phone,
                           c.email as customer_email,
                           s.name as service_name, s.duration_minutes, s.price,
                           p.name as professional_name
                    from appointments a
                    join customers c on c.id = a.customer_id
                    join services s on s.id = a.service_id
                    join professionals p on p.id = a.professional_id
                    where {' and '.join(clauses)}
                    order by a.starts_at asc
                    limit 500
                    """
                ),
                params,
            )
        ).mappings().all()
        return [self._row(row) for row in rows]

    async def get(self, appointment_id: str) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    select a.id::text, a.customer_id::text, a.service_id::text,
                           a.professional_id::text, a.starts_at, a.ends_at,
                           a.status, a.source, a.created_at,
                           c.name as customer_name, c.phone as customer_phone,
                           c.email as customer_email,
                           s.name as service_name, s.duration_minutes, s.price,
                           p.name as professional_name
                    from appointments a
                    join customers c on c.id = a.customer_id
                    join services s on s.id = a.service_id
                    join professionals p on p.id = a.professional_id
                    where a.id=:appointment_id::uuid
                    """
                ),
                {"appointment_id": appointment_id},
            )
        ).mappings().first()
        if row is None:
            raise APIError(
                "APPOINTMENT_NOT_FOUND",
                "Agendamento não encontrado.",
                404,
            )
        return self._row(row)

    async def update_status(
        self,
        appointment_id: str,
        status: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        if status not in {item.value for item in AppointmentStatus}:
            raise APIError(
                "APPOINTMENT_STATUS_INVALID",
                "Status de agendamento inválido.",
                422,
            )
        current = await self.session.scalar(
            text("select status from appointments where id=:id::uuid"),
            {"id": appointment_id},
        )
        if current is None:
            raise APIError(
                "APPOINTMENT_NOT_FOUND",
                "Agendamento não encontrado.",
                404,
            )
        if str(current) in FINAL_STATUSES and status not in FINAL_STATUSES:
            raise APIError(
                "APPOINTMENT_FINAL_STATUS",
                "Agendamento finalizado não pode voltar ao fluxo operacional.",
                409,
            )
        await self.session.execute(
            text("update appointments set status=:status where id=:id::uuid"),
            {"id": appointment_id, "status": status},
        )
        await self._add_history(appointment_id, status, reason)
        await NotificationService(
            self.session,
            public_base_url=self.public_base_url,
        ).schedule_for_appointment(
            appointment_id,
            f"appointment_{status.lower()}",
            reason=reason,
        )
        await self.session.commit()
        return await self.get(appointment_id)

    async def cancel(
        self,
        appointment_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return await self.update_status(
            appointment_id,
            AppointmentStatus.cancelled.value,
            reason,
        )

    async def availability(
        self,
        *,
        day: date,
        professional_id: str,
        service_id: str | None = None,
        slot_minutes: int = 30,
    ) -> list[dict[str, Any]]:
        duration = slot_minutes
        if service_id:
            service_duration = await self.session.scalar(
                text(
                    "select duration_minutes from services "
                    "where id=:id::uuid and active='true'"
                ),
                {"id": service_id},
            )
            duration = int(service_duration or slot_minutes)
        day_start = datetime.combine(day, time(hour=8), tzinfo=UTC)
        day_end = datetime.combine(day, time(hour=18), tzinfo=UTC)
        business_rows = (
            await self.session.execute(
                text(
                    """
                    select opens_at, closes_at from business_hours
                    where day_of_week=:dow and is_open=true
                      and (professional_id is null or professional_id=:professional_id::uuid)
                    order by professional_id nulls last
                    """
                ),
                {
                    "dow": int(day_start.strftime("%w")),
                    "professional_id": professional_id,
                },
            )
        ).mappings().all()
        windows: list[tuple[datetime, datetime]] = []
        if business_rows:
            for row in business_rows:
                windows.append(
                    (
                        datetime.combine(day, row["opens_at"], tzinfo=UTC),
                        datetime.combine(day, row["closes_at"], tzinfo=UTC),
                    )
                )
        else:
            windows.append((day_start, day_end))
        slots: list[dict[str, Any]] = []
        step = timedelta(minutes=slot_minutes)
        service_delta = timedelta(minutes=duration)
        for start, end_limit in windows:
            cursor = start
            while cursor + service_delta <= end_limit:
                end = cursor + service_delta
                blocked = await self._is_blocked(professional_id, cursor, end)
                overlap = await self._has_overlap(professional_id, cursor, end)
                slots.append(
                    {
                        "starts_at": cursor.isoformat(),
                        "ends_at": end.isoformat(),
                        "available": not blocked and not overlap,
                        "professional_id": professional_id,
                        "service_id": service_id,
                    }
                )
                cursor += step
        return slots
