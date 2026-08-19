from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.enums import AppointmentStatus
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.appointment_service import AppointmentService
from app.services.notification_service import NotificationService
from app.services.realtime_service import RealtimeEventService
from app.workers.celery_app import celery_app

router = APIRouter()


class AppointmentCreate(BaseModel):
    customer_id: str
    service_id: str
    professional_id: str
    starts_at: datetime
    ends_at: datetime
    source: str = Field(default="web", max_length=32)


class AppointmentQuickCreate(BaseModel):
    starts_at: datetime
    customer_id: str | None = None
    customer_name: str = Field(default="Cliente", min_length=2, max_length=160)
    customer_phone: str | None = Field(default=None, max_length=40)
    customer_email: EmailStr | None = None
    service_id: str | None = None
    service_name: str = Field(default="Atendimento", min_length=2, max_length=160)
    duration_minutes: int = Field(default=30, ge=5, le=720)
    price: float | None = Field(default=None, ge=0)
    professional_id: str | None = None
    professional_name: str = Field(default="Agenda geral", min_length=2, max_length=160)
    source: str = Field(default="tenant-web-quick", max_length=32)


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


def _public_base_url(context: TenantContext) -> str:
    scheme = "http" if context.hostname in {"localhost", "127.0.0.1"} else "https"
    return f"{scheme}://{context.hostname}"


async def _publish_realtime(
    context: TenantContext,
    session: AsyncSession,
    appointment_id: str,
    event_type: str,
    *,
    actor: str = "tenant-operator",
    extra: dict[str, Any] | None = None,
) -> None:
    event = await RealtimeEventService(session).emit_appointment(
        appointment_id,
        event_type,
        actor=actor,
        extra=extra,
    )
    event_id = str(event.get("id") or "") if event else ""
    if event_id:
        celery_app.send_task(
            "app.workers.tasks.dispatch_realtime_push",
            args=[context.tenant_id, event_id],
            queue="notifications",
        )


@router.get("")
async def list_appointments(
    day: date | None = Query(default=None),
    professional_id: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await AppointmentService(session).list_appointments(
        day=day,
        professional_id=professional_id,
        customer_id=customer_id,
        status=status,
    )
    return success(data)


@router.post("")
async def create_appointment(
    payload: AppointmentCreate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    appointment = await AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    ).create(payload.model_dump())
    await _publish_realtime(
        context,
        session,
        str(appointment.id),
        "appointment.created",
    )
    return success({"id": appointment.id, "status": appointment.status})


async def _quick_customer(
    session: AsyncSession,
    payload: AppointmentQuickCreate,
) -> str:
    if payload.customer_id:
        return payload.customer_id
    customer_id: str | None = None
    if payload.customer_phone:
        customer_id = await session.scalar(
            text(
                """
                select id::text from customers
                where phone=:phone
                order by created_at desc
                limit 1
                """
            ),
            {"phone": payload.customer_phone},
        )
    if customer_id:
        return str(customer_id)
    return str(
        await session.scalar(
            text(
                """
                insert into customers(name, phone, email, notes)
                values(:name, :phone, :email, 'Criado automaticamente pela agenda rápida')
                returning id::text
                """
            ),
            {
                "name": payload.customer_name,
                "phone": payload.customer_phone,
                "email": str(payload.customer_email) if payload.customer_email else None,
            },
        )
    )


async def _quick_service(
    session: AsyncSession,
    payload: AppointmentQuickCreate,
) -> tuple[str, int]:
    if payload.service_id:
        row = (
            await session.execute(
                text(
                    "select id::text, duration_minutes from services "
                    "where id=cast(:id as uuid)"
                ),
                {"id": payload.service_id},
            )
        ).mappings().first()
        if row:
            return str(row["id"]), int(row["duration_minutes"])
    row = (
        await session.execute(
            text(
                """
                select id::text, duration_minutes
                from services
                where lower(name)=lower(:name) and active='true'
                order by name
                limit 1
                """
            ),
            {"name": payload.service_name},
        )
    ).mappings().first()
    if row:
        return str(row["id"]), int(row["duration_minutes"])
    created = (
        await session.execute(
            text(
                """
                insert into services(name, duration_minutes, price, active)
                values(:name, :duration, :price, 'true')
                returning id::text, duration_minutes
                """
            ),
            {
                "name": payload.service_name,
                "duration": payload.duration_minutes,
                "price": payload.price,
            },
        )
    ).mappings().one()
    return str(created["id"]), int(created["duration_minutes"])


async def _quick_professional(
    session: AsyncSession,
    payload: AppointmentQuickCreate,
) -> str:
    if payload.professional_id:
        return payload.professional_id
    professional_id = await session.scalar(
        text(
            """
            select id::text from professionals
            where lower(name)=lower(:name)
            order by name
            limit 1
            """
        ),
        {"name": payload.professional_name},
    )
    if professional_id:
        return str(professional_id)
    return str(
        await session.scalar(
            text(
                "insert into professionals(name) values(:name) returning id::text"
            ),
            {"name": payload.professional_name},
        )
    )


@router.post("/quick")
async def create_quick_appointment(
    payload: AppointmentQuickCreate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    customer_id = await _quick_customer(session, payload)
    service_id, duration = await _quick_service(session, payload)
    professional_id = await _quick_professional(session, payload)
    await session.commit()

    starts_at = payload.starts_at
    ends_at = starts_at + timedelta(minutes=duration)
    appointment = await AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    ).create(
        {
            "customer_id": customer_id,
            "service_id": service_id,
            "professional_id": professional_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "source": payload.source,
        }
    )
    await _publish_realtime(
        context,
        session,
        str(appointment.id),
        "appointment.created",
        extra={"quick": True},
    )
    return success(
        {
            "id": appointment.id,
            "status": appointment.status,
            "customer_id": customer_id,
            "service_id": service_id,
            "professional_id": professional_id,
        }
    )


@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await AppointmentService(session).get(appointment_id))


@router.get("/{appointment_id}/history")
async def appointment_history(
    appointment_id: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    await AppointmentService(session).get(appointment_id)
    rows = (
        await session.execute(
            text(
                """
                select id::text, status, reason, created_at
                from appointment_status_history
                where appointment_id=:id::uuid
                order by created_at asc
                """
            ),
            {"id": appointment_id},
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.get("/{appointment_id}/notes")
async def appointment_notes(
    appointment_id: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    await AppointmentService(session).get(appointment_id)
    rows = (
        await session.execute(
            text(
                """
                select id::text, note, created_at
                from appointment_notes
                where appointment_id=:id::uuid
                order by created_at desc
                """
            ),
            {"id": appointment_id},
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.post("/{appointment_id}/notes")
async def add_appointment_note(
    appointment_id: str,
    payload: AppointmentNote,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    await AppointmentService(session).get(appointment_id)
    row = (
        await session.execute(
            text(
                """
                insert into appointment_notes(appointment_id, note)
                values(:id::uuid, :note)
                returning id::text, note, created_at
                """
            ),
            {"id": appointment_id, "note": payload.note},
        )
    ).mappings().one()
    await session.commit()
    return success(dict(row))


@router.patch("/{appointment_id}/status")
async def update_status(
    appointment_id: str,
    payload: AppointmentStatusUpdate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    ).update_status(
        appointment_id,
        payload.status,
        payload.reason,
    )
    event_type = {
        "CONFIRMED": "appointment.confirmed",
        "CANCELLED": "appointment.cancelled",
        "CHECKED_IN": "appointment.checked_in",
        "IN_PROGRESS": "appointment.in_progress",
        "COMPLETED": "appointment.completed",
        "NO_SHOW": "appointment.no_show",
    }.get(payload.status.upper(), "appointment.updated")
    await _publish_realtime(context, session, appointment_id, event_type)
    return success(data)


@router.post("/{appointment_id}/reschedule")
async def reschedule_appointment(
    appointment_id: str,
    payload: AppointmentReschedule,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    )
    current = await service.get(appointment_id)
    professional_id = payload.professional_id or str(current["professional_id"])
    await service._require_reference(
        "professionals",
        professional_id,
        "PROFESSIONAL_NOT_FOUND",
    )
    await service._ensure_slot_available(
        professional_id,
        payload.starts_at,
        payload.ends_at,
        ignore_appointment_id=appointment_id,
    )
    await session.execute(
        text(
            """
            update appointments
            set professional_id=:professional_id::uuid,
                starts_at=:starts_at,
                ends_at=:ends_at,
                status='AWAITING_CONFIRMATION'
            where id=:id::uuid
            """
        ),
        {
            "id": appointment_id,
            "professional_id": professional_id,
            "starts_at": payload.starts_at,
            "ends_at": payload.ends_at,
        },
    )
    await service._add_history(
        appointment_id,
        "RESCHEDULED",
        payload.reason or "Reagendado",
    )
    await service._add_history(
        appointment_id,
        AppointmentStatus.awaiting_confirmation.value,
        "Aguardando nova confirmação",
    )
    await NotificationService(
        session,
        public_base_url=_public_base_url(context),
    ).schedule_for_appointment(
        appointment_id,
        "appointment_rescheduled",
        reason=payload.reason,
        rotate_confirmation=True,
    )
    await session.commit()
    data = await service.get(appointment_id)
    await _publish_realtime(
        context,
        session,
        appointment_id,
        "appointment.rescheduled",
    )
    return success(data)


async def _action(
    appointment_id: str,
    status: AppointmentStatus,
    reason: str,
    context: TenantContext,
    session: AsyncSession,
) -> dict[str, Any]:
    data = await AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    ).update_status(
        appointment_id,
        status.value,
        reason,
    )
    event_type = {
        AppointmentStatus.confirmed: "appointment.confirmed",
        AppointmentStatus.checked_in: "appointment.checked_in",
        AppointmentStatus.in_progress: "appointment.in_progress",
        AppointmentStatus.completed: "appointment.completed",
        AppointmentStatus.no_show: "appointment.no_show",
        AppointmentStatus.cancelled: "appointment.cancelled",
    }.get(status, "appointment.updated")
    await _publish_realtime(context, session, appointment_id, event_type)
    return success(data)


@router.post("/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return await _action(
        appointment_id,
        AppointmentStatus.confirmed,
        "Confirmado pelo operador",
        context,
        session,
    )


@router.post("/{appointment_id}/check-in")
async def check_in_appointment(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return await _action(
        appointment_id,
        AppointmentStatus.checked_in,
        "Check-in realizado",
        context,
        session,
    )


@router.post("/{appointment_id}/start")
async def start_appointment(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return await _action(
        appointment_id,
        AppointmentStatus.in_progress,
        "Atendimento iniciado",
        context,
        session,
    )


@router.post("/{appointment_id}/complete")
async def complete_appointment(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return await _action(
        appointment_id,
        AppointmentStatus.completed,
        "Atendimento concluído",
        context,
        session,
    )


@router.post("/{appointment_id}/no-show")
async def no_show_appointment(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return await _action(
        appointment_id,
        AppointmentStatus.no_show,
        "Cliente não compareceu",
        context,
        session,
    )


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: str,
    payload: AppointmentCancel,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    ).cancel(appointment_id, payload.reason)
    await _publish_realtime(
        context,
        session,
        appointment_id,
        "appointment.cancelled",
    )
    return success(data)
