from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.enums import AppointmentStatus
from app.core.responses import success
from app.services.appointment_service import AppointmentService
from app.services.notification_service import NotificationService

router = APIRouter()


class AppointmentCreate(BaseModel):
    customer_id: str
    service_id: str
    professional_id: str
    starts_at: datetime
    ends_at: datetime
    source: str = Field(default="web", max_length=32)


class AppointmentStatusUpdate(BaseModel):
    status: str = Field(min_length=3, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class AppointmentCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AppointmentReschedule(BaseModel):
    starts_at: datetime
    ends_at: datetime
    professional_id: str | None = None
    reason: str | None = Field(default=None, max_length=500)


class AppointmentNote(BaseModel):
    note: str = Field(min_length=1, max_length=4000)


@router.get("")
async def list_appointments(
    day: date | None = Query(default=None),
    professional_id: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await AppointmentService(session).list_appointments(day=day, professional_id=professional_id, customer_id=customer_id, status=status)
    return success(data)


@router.post("")
async def create_appointment(payload: AppointmentCreate, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    appointment = await AppointmentService(session).create(payload.model_dump())
    return success({"id": appointment.id, "status": appointment.status})


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return success(await AppointmentService(session).get(appointment_id))


@router.get("/{appointment_id}/history")
async def appointment_history(appointment_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    await AppointmentService(session).get(appointment_id)
    rows = (
        await session.execute(
            text("select id::text, status, reason, created_at from appointment_status_history where appointment_id=:id::uuid order by created_at asc"),
            {"id": appointment_id},
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.get("/{appointment_id}/notes")
async def appointment_notes(appointment_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    await AppointmentService(session).get(appointment_id)
    rows = (
        await session.execute(
            text("select id::text, note, created_at from appointment_notes where appointment_id=:id::uuid order by created_at desc"),
            {"id": appointment_id},
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.post("/{appointment_id}/notes")
async def add_appointment_note(appointment_id: str, payload: AppointmentNote, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    await AppointmentService(session).get(appointment_id)
    row = (
        await session.execute(
            text("insert into appointment_notes(appointment_id, note) values(:id::uuid, :note) returning id::text, note, created_at"),
            {"id": appointment_id, "note": payload.note},
        )
    ).mappings().one()
    await session.commit()
    return success(dict(row))


@router.patch("/{appointment_id}/status")
async def update_status(appointment_id: str, payload: AppointmentStatusUpdate, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return success(await AppointmentService(session).update_status(appointment_id, payload.status, payload.reason))


@router.post("/{appointment_id}/reschedule")
async def reschedule_appointment(appointment_id: str, payload: AppointmentReschedule, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    service = AppointmentService(session)
    current = await service.get(appointment_id)
    professional_id = payload.professional_id or str(current["professional_id"])
    await service._require_reference("professionals", professional_id, "PROFESSIONAL_NOT_FOUND")
    await service._ensure_slot_available(professional_id, payload.starts_at, payload.ends_at, ignore_appointment_id=appointment_id)
    await session.execute(
        text("update appointments set professional_id=:professional_id::uuid, starts_at=:starts_at, ends_at=:ends_at, status='RESCHEDULED' where id=:id::uuid"),
        {"id": appointment_id, "professional_id": professional_id, "starts_at": payload.starts_at, "ends_at": payload.ends_at},
    )
    await service._add_history(appointment_id, AppointmentStatus.rescheduled.value, payload.reason or "Reagendado")
    await NotificationService(session).schedule_for_appointment(appointment_id, "appointment_created", reason=payload.reason)
    await session.commit()
    return success(await service.get(appointment_id))


async def _action(appointment_id: str, status: AppointmentStatus, reason: str, session: AsyncSession) -> dict[str, Any]:
    return success(await AppointmentService(session).update_status(appointment_id, status.value, reason))


@router.post("/{appointment_id}/confirm")
async def confirm_appointment(appointment_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return await _action(appointment_id, AppointmentStatus.confirmed, "Confirmado pelo operador", session)


@router.post("/{appointment_id}/check-in")
async def check_in_appointment(appointment_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return await _action(appointment_id, AppointmentStatus.checked_in, "Check-in realizado", session)


@router.post("/{appointment_id}/start")
async def start_appointment(appointment_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return await _action(appointment_id, AppointmentStatus.in_progress, "Atendimento iniciado", session)


@router.post("/{appointment_id}/complete")
async def complete_appointment(appointment_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return await _action(appointment_id, AppointmentStatus.completed, "Atendimento concluído", session)


@router.post("/{appointment_id}/no-show")
async def no_show_appointment(appointment_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return await _action(appointment_id, AppointmentStatus.no_show, "Cliente não compareceu", session)


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: str, payload: AppointmentCancel, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return success(await AppointmentService(session).cancel(appointment_id, payload.reason))
