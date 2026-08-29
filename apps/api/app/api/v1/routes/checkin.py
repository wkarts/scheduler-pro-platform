from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.enums import AppointmentStatus
from app.core.errors import APIError
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.appointment_service import AppointmentService
from app.services.booking_parameters_service import BookingParametersService
from app.services.notification_service import NotificationService
from app.services.realtime_service import RealtimeEventService
from app.workers.celery_app import celery_app

router = APIRouter()


def _public_base_url(context: TenantContext) -> str:
    scheme = "http" if context.hostname in {"localhost", "127.0.0.1"} else "https"
    return f"{scheme}://{context.hostname}"


async def _publish_realtime(
    context: TenantContext,
    session: AsyncSession,
    appointment_id: str,
    *,
    completed_by_checkin: bool,
) -> None:
    event = await RealtimeEventService(session).emit_appointment(
        appointment_id,
        "appointment.checked_in",
        actor="tenant-check-in-center",
        extra={
            "source": "check-in-center",
            "completed_by_checkin": completed_by_checkin,
        },
    )
    event_id = str(event.get("id") or "") if event else ""
    if event_id:
        celery_app.send_task(
            "app.workers.tasks.dispatch_realtime_push",
            args=[context.tenant_id, event_id],
            queue="notifications",
        )


async def _schedule_check_in_notification(
    session: AsyncSession,
    appointment_id: str,
    *,
    public_base_url: str,
    completed_by_checkin: bool,
) -> None:
    notifications = NotificationService(session, public_base_url=public_base_url)
    context = await notifications._appointment_context(appointment_id)
    if not context:
        return

    service_line = (
        f"Serviço: {context['service_name']}\n" if context.get("service_name") else ""
    )
    closing_line = (
        "Seu atendimento foi registrado como realizado."
        if completed_by_checkin
        else "Seu atendimento está confirmado na recepção."
    )
    message = (
        f"Olá, {context.get('customer_name') or 'cliente'}!\n\n"
        "Seu check-in foi registrado.\n"
        f"{service_line}"
        f"Profissional: {context.get('professional_name') or 'Agenda geral'}\n"
        f"Data/Horário: {context.get('starts_at_br') or ''}.\n\n"
        f"{closing_line}"
    ).strip()
    payload: dict[str, Any] = {
        **context,
        "message": message,
        "completed_by_checkin": completed_by_checkin,
    }
    scheduled_at = datetime.now(UTC)

    phone = str(context.get("customer_phone") or "").strip()
    if phone:
        await notifications._enqueue(
            appointment_id=appointment_id,
            template_key="appointment_checked_in",
            channel="whatsapp",
            recipient=phone,
            payload=payload,
            scheduled_at=scheduled_at,
        )

    email = str(context.get("customer_email") or "").strip()
    if email and await notifications._email_enabled():
        await notifications._enqueue(
            appointment_id=appointment_id,
            template_key="appointment_checked_in_email",
            channel="email",
            recipient=email,
            payload={**payload, "subject": "Check-in registrado — Scheduler Pro"},
            scheduled_at=scheduled_at,
        )


@router.post("/{appointment_id}")
async def check_in(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Registra a chegada real; o relógio nunca executa esta transição sozinho."""
    parameters = await BookingParametersService(session).get()
    simplified = parameters.get("checkin_flow_mode") == "SIMPLE"
    service = AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    )
    current = await service.get(appointment_id)
    current_status = str(current.get("status") or "").upper()

    if current_status == AppointmentStatus.checked_in.value:
        return success(current)
    if simplified and current_status == AppointmentStatus.completed.value:
        return success(current)
    if current_status != AppointmentStatus.confirmed.value:
        raise APIError(
            "CHECK_IN_REQUIRES_CONFIRMATION",
            "O check-in só pode ser realizado em um agendamento confirmado.",
            409,
            {"current_status": current_status},
        )

    next_status = (
        AppointmentStatus.completed.value
        if simplified
        else AppointmentStatus.checked_in.value
    )
    await session.execute(
        text(
            "update appointments set status=:status "
            "where id=cast(:id as uuid) and status=:expected"
        ),
        {
            "id": appointment_id,
            "status": next_status,
            "expected": AppointmentStatus.confirmed.value,
        },
    )
    await service._add_history(
        appointment_id,
        AppointmentStatus.checked_in.value,
        (
            "Check-in simplificado realizado pela Central de Check-in"
            if simplified
            else "Check-in realizado pela Central de Check-in"
        ),
    )
    if simplified:
        await service._add_history(
            appointment_id,
            AppointmentStatus.completed.value,
            "Atendimento concluído automaticamente pelo fluxo simplificado de Check-in",
        )
    await _schedule_check_in_notification(
        session,
        appointment_id,
        public_base_url=_public_base_url(context),
        completed_by_checkin=simplified,
    )
    await session.commit()
    await _publish_realtime(
        context,
        session,
        appointment_id,
        completed_by_checkin=simplified,
    )
    return success(await service.get(appointment_id))
