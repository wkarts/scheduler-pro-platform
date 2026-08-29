from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AppointmentStatus
from app.core.errors import APIError
from app.db.models_tenant import Appointment
from app.services.notification_service import NotificationService
from app.services.phone_normalization import PhoneNormalizationService

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

SERVICE_MODES = {"DISABLED", "OPTIONAL", "REQUIRED"}


class AppointmentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        public_base_url: str | None = None,
        timezone: str | None = None,
    ) -> None:
        self.session = session
        self.public_base_url = public_base_url
        timezone_name = str(
            timezone
            or session.info.get("tenant_timezone")
            or "America/Bahia"
        )
        try:
            self.timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            self.timezone = ZoneInfo("America/Bahia")

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    @staticmethod
    def _bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "sim", "on"}

    async def _setting(self, key: str, default: Any) -> Any:
        value = await self.session.scalar(
            text("select value from tenant_settings where key=:key limit 1"),
            {"key": key},
        )
        return default if value is None else value

    async def service_mode(self) -> str:
        mode = str(await self._setting("booking_service_mode", "REQUIRED")).upper()
        return mode if mode in SERVICE_MODES else "REQUIRED"

    async def default_duration_minutes(self) -> int:
        value = int(await self._setting("default_appointment_duration_minutes", 60))
        return max(5, min(720, value))

    async def capacity(self, source: str = "internal") -> int:
        public = str(source or "").lower().startswith("public")
        allow_key = (
            "allow_simultaneous_public_booking"
            if public
            else "allow_simultaneous_internal_booking"
        )
        if not self._bool(await self._setting(allow_key, False), False):
            return 1
        configured = int(await self._setting("simultaneous_booking_capacity", 1))
        return max(1, min(100, configured))

    async def _require_reference(self, table: str, entity_id: str, code: str) -> None:
        exists = await self.session.scalar(
            text(f"select exists(select 1 from {table} where id=cast(:id as uuid))"),
            {"id": entity_id},
        )
        if not exists:
            raise APIError(code, "Registro relacionado não encontrado.", 404)

    async def _validate_customer(self, customer_id: str) -> None:
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
                "Todo agendamento exige o nome do cliente.",
                422,
            )
        phone = str(row["phone_normalized"] or row["phone"] or "").strip()
        if not phone:
            raise APIError(
                "APPOINTMENT_CUSTOMER_PHONE_REQUIRED",
                "Todo agendamento exige telefone/WhatsApp.",
                422,
            )
        normalizer = await PhoneNormalizationService.from_session(self.session)
        await normalizer.normalize_customer_phone(
            self.session,
            customer_id=customer_id,
            value=phone,
        )

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
        local_start = self._aware(starts_at).astimezone(self.timezone)
        local_end = self._aware(ends_at).astimezone(self.timezone)
        if local_start.date() != local_end.date():
            return False
        dow = int(local_start.strftime("%w"))
        result = await self.session.scalar(
            text(
                """
                select exists(
                  select 1 from business_hours
                  where is_open = true
                    and day_of_week = :dow
                    and (
                      professional_id is null
                      or professional_id = cast(:professional_id as uuid)
                    )
                    and cast(:start_time as time) >= opens_at
                    and cast(:end_time as time) <= closes_at
                )
                """
            ),
            {
                "dow": dow,
                "professional_id": professional_id,
                "start_time": local_start.timetz().replace(tzinfo=None),
                "end_time": local_end.timetz().replace(tzinfo=None),
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
                  where (
                    professional_id is null
                    or professional_id = cast(:professional_id as uuid)
                  )
                    and tstzrange(starts_at, ends_at, '[)')
                        && tstzrange(:starts_at, :ends_at, '[)')
                )
                """
            ),
            {
                "professional_id": professional_id,
                "starts_at": self._aware(starts_at),
                "ends_at": self._aware(ends_at),
            },
        )
        return bool(result)

    async def _overlap_count(
        self,
        professional_id: str,
        starts_at: datetime,
        ends_at: datetime,
        *,
        ignore_appointment_id: str | None = None,
    ) -> int:
        base = """
            select count(*)
            from appointments
            where professional_id = cast(:professional_id as uuid)
              and status = any(:busy_statuses)
              and tstzrange(starts_at, ends_at, '[)')
                  && tstzrange(:starts_at, :ends_at, '[)')
        """
        params: dict[str, Any] = {
            "professional_id": professional_id,
            "starts_at": self._aware(starts_at),
            "ends_at": self._aware(ends_at),
            "busy_statuses": list(BUSY_STATUSES),
        }
        if ignore_appointment_id:
            base += " and id <> cast(:ignore_appointment_id as uuid)"
            params["ignore_appointment_id"] = ignore_appointment_id
        return int(await self.session.scalar(text(base), params) or 0)

    async def _has_overlap(
        self,
        professional_id: str,
        starts_at: datetime,
        ends_at: datetime,
        *,
        ignore_appointment_id: str | None = None,
    ) -> bool:
        return (
            await self._overlap_count(
                professional_id,
                starts_at,
                ends_at,
                ignore_appointment_id=ignore_appointment_id,
            )
        ) > 0

    async def _lock_professional_capacity(self, professional_id: str) -> None:
        # Uma única chave por profissional serializa também overlaps parciais
        # (09:00-10:00 versus 09:30-10:30). Lock por slot exato não seria seguro.
        await self.session.execute(
            text("select pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"scheduler-pro:appointment-capacity:{professional_id}"},
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
        if not await self._is_inside_business_hours(professional_id, starts_at, ends_at):
            raise APIError(
                "APPOINTMENT_OUTSIDE_BUSINESS_HOURS",
                "Horário fora do expediente.",
                409,
            )
        if await self._is_blocked(professional_id, starts_at, ends_at):
            raise APIError("APPOINTMENT_BLOCKED_PERIOD", "Horário bloqueado.", 409)

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

    async def create(self, payload: dict[str, Any]) -> Appointment:
        payload = dict(payload)
        payload["starts_at"] = self._aware(payload["starts_at"])
        payload["ends_at"] = self._aware(payload["ends_at"])
        service_mode = await self.service_mode()
        service_id = payload.get("service_id")
        if service_mode == "DISABLED":
            payload["service_id"] = None
            service_id = None
        elif not service_id and service_mode == "REQUIRED":
            raise APIError(
                "APPOINTMENT_SERVICE_REQUIRED",
                "Selecione um serviço para continuar.",
                422,
            )

        try:
            await self._validate_customer(str(payload["customer_id"]))
            if service_id:
                await self._require_reference(
                    "services",
                    str(service_id),
                    "SERVICE_NOT_FOUND",
                )
            await self._require_reference(
                "professionals",
                str(payload["professional_id"]),
                "PROFESSIONAL_NOT_FOUND",
            )
            await self._ensure_slot_available(
                str(payload["professional_id"]),
                payload["starts_at"],
                payload["ends_at"],
                source=str(payload.get("source") or "internal"),
            )
            appointment = Appointment(
                **payload,
                status=AppointmentStatus.awaiting_confirmation.value,
            )
            self.session.add(appointment)
            await self.session.flush()
            await self._add_history(
                str(appointment.id),
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
            await self.session.commit()
            return appointment
        except IntegrityError as exc:
            await self.session.rollback()
            raise APIError(
                "APPOINTMENT_CREATE_CONFLICT",
                "Não foi possível gravar o agendamento devido a um conflito de dados.",
                409,
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

    async def _add_history(
        self,
        appointment_id: str,
        status: str,
        reason: str | None = None,
    ) -> None:
        await self.session.execute(
            text(
                "insert into appointment_status_history(appointment_id, status, reason) "
                "values(cast(:appointment_id as uuid), :status, :reason)"
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
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        professional_id: str | None = None,
        customer_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: dict[str, Any] = {}
        if starts_at is not None or ends_at is not None:
            if starts_at is None or ends_at is None:
                raise APIError("APPOINTMENT_RANGE_INVALID", "Informe starts_at e ends_at juntos.", 422)
            range_start = starts_at if starts_at.tzinfo else starts_at.replace(tzinfo=self.timezone)
            range_end = ends_at if ends_at.tzinfo else ends_at.replace(tzinfo=self.timezone)
            range_start = range_start.astimezone(UTC)
            range_end = range_end.astimezone(UTC)
            if range_end <= range_start:
                raise APIError("APPOINTMENT_RANGE_INVALID", "Período de agenda inválido.", 422)
            if range_end - range_start > timedelta(days=370):
                raise APIError("APPOINTMENT_RANGE_TOO_LARGE", "Consulte no máximo 370 dias por vez.", 422)
            clauses.append("a.starts_at >= :range_start and a.starts_at < :range_end")
            params["range_start"] = range_start
            params["range_end"] = range_end
        elif day:
            local_start = datetime.combine(day, time.min, tzinfo=self.timezone)
            local_end = local_start + timedelta(days=1)
            clauses.append("a.starts_at >= :day_start and a.starts_at < :day_end")
            params["day_start"] = local_start.astimezone(UTC)
            params["day_end"] = local_end.astimezone(UTC)
        if professional_id:
            clauses.append("a.professional_id = cast(:professional_id as uuid)")
            params["professional_id"] = professional_id
        if customer_id:
            clauses.append("a.customer_id = cast(:customer_id as uuid)")
            params["customer_id"] = customer_id
        if status:
            clauses.append("a.status = :status")
            params["status"] = status
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select a.id::text, a.customer_id::text, a.service_id::text,
                           a.professional_id::text, a.starts_at,
                           case when a.ends_at is null or a.ends_at <= a.starts_at then a.starts_at + interval '60 minutes' else a.ends_at end as ends_at,
                           a.status, a.source, a.created_at,
                           coalesce(c.name,'Cliente legado') as customer_name,
                           c.phone as customer_phone, c.email as customer_email,
                           coalesce(s.name,'Atendimento') as service_name,
                           case when coalesce(s.duration_minutes, 0) > 0 then s.duration_minutes else greatest(5, extract(epoch from ((case when a.ends_at is null or a.ends_at <= a.starts_at then a.starts_at + interval '60 minutes' else a.ends_at end)-a.starts_at))/60)::integer end as duration_minutes,
                           s.price, coalesce(p.name,'Agenda geral') as professional_name
                    from appointments a
                    left join customers c on c.id = a.customer_id
                    left join services s on s.id = a.service_id
                    left join professionals p on p.id = a.professional_id
                    where {' and '.join(clauses)}
                    order by a.starts_at asc
                    limit 2000
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
                           a.professional_id::text, a.starts_at,
                           case when a.ends_at is null or a.ends_at <= a.starts_at then a.starts_at + interval '60 minutes' else a.ends_at end as ends_at,
                           a.status, a.source, a.created_at,
                           coalesce(c.name,'Cliente legado') as customer_name,
                           c.phone as customer_phone, c.email as customer_email,
                           coalesce(s.name,'Atendimento') as service_name,
                           case when coalesce(s.duration_minutes, 0) > 0 then s.duration_minutes else greatest(5, extract(epoch from ((case when a.ends_at is null or a.ends_at <= a.starts_at then a.starts_at + interval '60 minutes' else a.ends_at end)-a.starts_at))/60)::integer end as duration_minutes,
                           s.price, coalesce(p.name,'Agenda geral') as professional_name
                    from appointments a
                    left join customers c on c.id = a.customer_id
                    left join services s on s.id = a.service_id
                    left join professionals p on p.id = a.professional_id
                    where a.id=cast(:appointment_id as uuid)
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
            text("select status from appointments where id=cast(:id as uuid)"),
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
            text(
                "update appointments set status=:status "
                "where id=cast(:id as uuid)"
            ),
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
        if status == AppointmentStatus.confirmed.value:
            await self.session.execute(
                text(
                    """
                    update appointment_confirmation_requests
                    set state='CONFIRMED', response='CONFIRMED',
                        responded_at=coalesce(responded_at, now()), updated_at=now()
                    where appointment_id=cast(:id as uuid) and state='PENDING'
                    """
                ),
                {"id": appointment_id},
            )
        elif status in FINAL_STATUSES:
            await self.session.execute(
                text(
                    """
                    update appointment_confirmation_requests
                    set state=case
                            when :status='CANCELLED' then 'CANCELLED'
                            else 'REVOKED'
                        end,
                        response=case
                            when :status='CANCELLED' then 'CANCELLED'
                            else response
                        end,
                        responded_at=coalesce(responded_at, now()), updated_at=now()
                    where appointment_id=cast(:id as uuid) and state='PENDING'
                    """
                ),
                {"id": appointment_id, "status": status},
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
        source: str = "internal",
    ) -> list[dict[str, Any]]:
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
        elif await self.service_mode() != "REQUIRED":
            duration = await self.default_duration_minutes()

        capacity = await self.capacity(source)
        local_day_start = datetime.combine(day, time(hour=8), tzinfo=self.timezone)
        local_day_end = datetime.combine(day, time(hour=18), tzinfo=self.timezone)
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
        windows: list[tuple[datetime, datetime]] = []
        if business_rows:
            for row in business_rows:
                local_start = datetime.combine(
                    day,
                    row["opens_at"],
                    tzinfo=self.timezone,
                )
                local_end = datetime.combine(
                    day,
                    row["closes_at"],
                    tzinfo=self.timezone,
                )
                windows.append(
                    (local_start.astimezone(UTC), local_end.astimezone(UTC))
                )
        else:
            windows.append(
                (local_day_start.astimezone(UTC), local_day_end.astimezone(UTC))
            )
        slots: list[dict[str, Any]] = []
        step = timedelta(minutes=slot_minutes)
        service_delta = timedelta(minutes=duration)
        for start, end_limit in windows:
            cursor = start
            while cursor + service_delta <= end_limit:
                end = cursor + service_delta
                blocked = await self._is_blocked(professional_id, cursor, end)
                occupied = await self._overlap_count(professional_id, cursor, end)
                slots.append(
                    {
                        "starts_at": cursor.isoformat(),
                        "ends_at": end.isoformat(),
                        "available": not blocked and occupied < capacity,
                        "professional_id": professional_id,
                        "service_id": service_id,
                        "capacity": capacity,
                        "occupied": occupied,
                        "remaining_capacity": max(0, capacity - occupied),
                    }
                )
                cursor += step
        return slots
