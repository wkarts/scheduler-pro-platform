from __future__ import annotations

import calendar
import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_tenant_context, get_tenant_session
from app.api.v1.routes.appointments import (
    AppointmentQuickCreate,
    _publish_realtime,
    _public_base_url,
    _quick_customer,
    _quick_professional,
    _quick_service,
)
from app.core.errors import APIError
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.appointment_service import AppointmentService, FINAL_STATUSES
from app.services.notification_service import NotificationService

router = APIRouter()


class RecurringAppointmentCreate(AppointmentQuickCreate):
    repeat_every_weeks: int = Field(default=1, ge=1, le=12)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    months_ahead: int | None = Field(default=12, ge=1, le=36)
    until: date | None = None
    max_occurrences: int = Field(default=104, ge=1, le=366)
    skip_sundays: bool = True
    skip_dates: list[date] = Field(default_factory=list, max_length=500)
    conflict_policy: Literal["skip", "abort"] = "skip"

    @model_validator(mode="after")
    def validate_weekdays(self) -> "RecurringAppointmentCreate":
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("Dias da semana devem estar entre 0 (segunda) e 6 (domingo).")
        if self.until is None and self.months_ahead is None:
            self.months_ahead = 12
        return self


class AppointmentSwapRequest(BaseModel):
    first_id: str
    second_id: str
    reason: str | None = Field(default="Permuta de horários pelo gestor", max_length=500)


class AppointmentReuseRequest(BaseModel):
    customer_id: str | None = None
    customer_name: str = Field(min_length=2, max_length=160)
    customer_phone: str | None = Field(default=None, max_length=40)
    customer_email: EmailStr | None = None
    service_id: str | None = None
    service_name: str | None = Field(default=None, max_length=160)
    duration_minutes: int | None = Field(default=None, ge=5, le=720)
    price: float | None = Field(default=None, ge=0)
    professional_id: str | None = None
    professional_name: str | None = Field(default=None, max_length=160)


def _tenant_timezone(context: TenantContext) -> ZoneInfo:
    try:
        return ZoneInfo(context.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/Bahia")


def _add_months(value: date, months: int) -> date:
    index = value.month - 1 + months
    year = value.year + index // 12
    month = index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _candidate_starts(payload: RecurringAppointmentCreate, context: TenantContext) -> list[datetime]:
    timezone = _tenant_timezone(context)
    initial = payload.starts_at
    if initial.tzinfo is None:
        initial = initial.replace(tzinfo=timezone)
    local_initial = initial.astimezone(timezone)
    weekdays = sorted(set(payload.weekdays or [local_initial.weekday()]))
    skip_dates = set(payload.skip_dates)
    horizon = payload.until or _add_months(local_initial.date(), int(payload.months_ahead or 12))
    if horizon < local_initial.date():
        raise APIError("RECURRENCE_PERIOD_INVALID", "A data final deve ser posterior ao primeiro agendamento.", 422)

    starts: list[datetime] = []
    cursor = local_initial.date()
    anchor_monday = cursor - timedelta(days=cursor.weekday())
    local_time = time(local_initial.hour, local_initial.minute, local_initial.second, local_initial.microsecond)
    while cursor <= horizon and len(starts) < payload.max_occurrences:
        week_index = max(0, (cursor - anchor_monday).days // 7)
        eligible_week = week_index % payload.repeat_every_weeks == 0
        if eligible_week and cursor.weekday() in weekdays:
            if not (payload.skip_sundays and cursor.weekday() == 6) and cursor not in skip_dates:
                candidate = datetime.combine(cursor, local_time, tzinfo=timezone)
                if candidate >= local_initial:
                    starts.append(candidate.astimezone(UTC))
        cursor += timedelta(days=1)
    return starts


def _friendly_operation_error(exc: APIError) -> str:
    mapping = {
        "APPOINTMENT_SLOT_UNAVAILABLE": "Horário já ocupado",
        "APPOINTMENT_OUTSIDE_BUSINESS_HOURS": "Fora do expediente",
        "APPOINTMENT_BLOCKED_PERIOD": "Horário bloqueado",
        "CUSTOMER_NOT_FOUND": "Cliente não encontrado",
        "SERVICE_NOT_FOUND": "Serviço não encontrado",
        "PROFESSIONAL_NOT_FOUND": "Profissional não encontrado",
    }
    return mapping.get(exc.code, exc.message)


@router.post("/recurring")
async def create_recurring_appointments(
    payload: RecurringAppointmentCreate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    customer_id = await _quick_customer(session, payload)
    service_id, service_duration = await _quick_service(session, payload)
    professional_id = await _quick_professional(session, payload)
    await session.commit()

    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    service = AppointmentService(
        session,
        public_base_url=_public_base_url(context),
        timezone=context.timezone,
    )
    for starts_at in _candidate_starts(payload, context):
        ends_at = starts_at + timedelta(minutes=service_duration)
        try:
            appointment = await service.create(
                {
                    "customer_id": customer_id,
                    "service_id": service_id,
                    "professional_id": professional_id,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "source": "tenant-web-recurring",
                }
            )
            appointment_id = str(appointment.id)
            await _publish_realtime(
                context,
                session,
                appointment_id,
                "appointment.created",
                extra={"recurring": True},
            )
            created.append({"id": appointment_id, "starts_at": starts_at, "status": appointment.status})
        except APIError as exc:
            skipped.append({"starts_at": starts_at, "code": exc.code, "reason": _friendly_operation_error(exc)})
            if payload.conflict_policy == "abort":
                break

    return {
        "success": True,
        "data": {
            "created": created,
            "skipped": skipped,
            "summary": {
                "requested": len(created) + len(skipped),
                "created": len(created),
                "skipped": len(skipped),
            },
            "customer_id": customer_id,
            "service_id": service_id,
            "professional_id": professional_id,
        },
    }


@router.post("/swap")
async def swap_appointment_slots(
    payload: AppointmentSwapRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    if payload.first_id == payload.second_id:
        raise APIError("APPOINTMENT_SWAP_SAME", "Selecione dois agendamentos diferentes.", 422)

    service = AppointmentService(session, public_base_url=_public_base_url(context), timezone=context.timezone)
    first = await service.get(payload.first_id)
    second = await service.get(payload.second_id)
    if first["status"] in FINAL_STATUSES or second["status"] in FINAL_STATUSES:
        raise APIError("APPOINTMENT_SWAP_FINAL", "Agendamentos concluídos, cancelados ou faltas não podem ser permutados.", 409)

    first_duration = first["ends_at"] - first["starts_at"]
    sentinel_start = datetime.now(UTC) + timedelta(days=36500, seconds=abs(hash(payload.first_id)) % 50000)
    sentinel_end = sentinel_start + first_duration

    try:
        await session.execute(
            text(
                """
                update appointments set starts_at=:starts_at, ends_at=:ends_at
                where id=cast(:id as uuid)
                """
            ),
            {"id": payload.first_id, "starts_at": sentinel_start, "ends_at": sentinel_end},
        )

        await service._ensure_slot_available(
            str(first["professional_id"]),
            first["starts_at"],
            first["ends_at"],
            ignore_appointment_id=payload.second_id,
        )
        await session.execute(
            text(
                """
                update appointments
                set professional_id=cast(:professional_id as uuid), starts_at=:starts_at,
                    ends_at=:ends_at, status='AWAITING_CONFIRMATION'
                where id=cast(:id as uuid)
                """
            ),
            {
                "id": payload.second_id,
                "professional_id": first["professional_id"],
                "starts_at": first["starts_at"],
                "ends_at": first["ends_at"],
            },
        )

        await service._ensure_slot_available(
            str(second["professional_id"]),
            second["starts_at"],
            second["ends_at"],
            ignore_appointment_id=payload.first_id,
        )
        await session.execute(
            text(
                """
                update appointments
                set professional_id=cast(:professional_id as uuid), starts_at=:starts_at,
                    ends_at=:ends_at, status='AWAITING_CONFIRMATION'
                where id=cast(:id as uuid)
                """
            ),
            {
                "id": payload.first_id,
                "professional_id": second["professional_id"],
                "starts_at": second["starts_at"],
                "ends_at": second["ends_at"],
            },
        )

        for appointment_id in (payload.first_id, payload.second_id):
            await service._add_history(appointment_id, "RESCHEDULED", payload.reason)
            await service._add_history(appointment_id, "AWAITING_CONFIRMATION", "Aguardando confirmação após permuta")
            await NotificationService(session, public_base_url=_public_base_url(context)).schedule_for_appointment(
                appointment_id,
                "appointment_rescheduled",
                reason=payload.reason,
                rotate_confirmation=True,
            )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    await _publish_realtime(context, session, payload.first_id, "appointment.rescheduled", extra={"swap": payload.second_id})
    await _publish_realtime(context, session, payload.second_id, "appointment.rescheduled", extra={"swap": payload.first_id})
    return {"success": True, "data": {"first": await service.get(payload.first_id), "second": await service.get(payload.second_id)}}


@router.post("/{appointment_id}/reuse")
async def reuse_cancelled_slot(
    appointment_id: str,
    payload: AppointmentReuseRequest,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = AppointmentService(session, public_base_url=_public_base_url(context), timezone=context.timezone)
    original = await service.get(appointment_id)
    if original["status"] not in {"CANCELLED", "NO_SHOW"}:
        raise APIError("APPOINTMENT_REUSE_NOT_FREE", "Cancele ou libere o agendamento antes de reutilizar esse horário.", 409)
    if original["starts_at"] <= datetime.now(UTC):
        raise APIError("APPOINTMENT_REUSE_PAST", "Não é possível reutilizar um horário que já passou.", 409)

    quick = AppointmentQuickCreate(
        starts_at=original["starts_at"],
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        service_id=payload.service_id or str(original["service_id"]),
        service_name=payload.service_name or str(original["service_name"]),
        duration_minutes=payload.duration_minutes or int(original["duration_minutes"] or 30),
        price=payload.price if payload.price is not None else original["price"],
        professional_id=payload.professional_id or str(original["professional_id"]),
        professional_name=payload.professional_name or str(original["professional_name"]),
        source="tenant-web-reuse",
    )
    customer_id = await _quick_customer(session, quick)
    service_id, duration = await _quick_service(session, quick)
    professional_id = await _quick_professional(session, quick)
    await session.commit()

    appointment = await service.create(
        {
            "customer_id": customer_id,
            "service_id": service_id,
            "professional_id": professional_id,
            "starts_at": original["starts_at"],
            "ends_at": original["starts_at"] + timedelta(minutes=duration),
            "source": "tenant-web-reuse",
        }
    )
    new_id = str(appointment.id)
    await _publish_realtime(context, session, new_id, "appointment.created", extra={"reused_from": appointment_id})
    return {"success": True, "data": {"id": new_id, "reused_from": appointment_id, "status": appointment.status}}


@router.delete("/{appointment_id}/permanent")
async def permanently_delete_appointment(
    appointment_id: str,
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = AppointmentService(session)
    snapshot = await service.get(appointment_id)
    if snapshot["status"] not in FINAL_STATUSES:
        raise APIError("APPOINTMENT_DELETE_ACTIVE", "Cancele ou finalize o agendamento antes de excluí-lo definitivamente.", 409)

    await session.execute(
        text(
            """
            insert into audit_logs(user_id, action, result, metadata)
            values(cast(:user_id as uuid), 'appointment.permanent_delete', 'SUCCESS', cast(:metadata as jsonb))
            """
        ),
        {"user_id": principal.user_id, "metadata": json.dumps(snapshot, default=str, ensure_ascii=False)},
    )
    await session.execute(text("delete from appointments where id=cast(:id as uuid)"), {"id": appointment_id})
    await session.commit()
    return {"success": True, "data": {"deleted": True, "appointment_id": appointment_id}}
