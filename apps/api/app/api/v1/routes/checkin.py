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

MANUAL_CONFIRMABLE_STATUSES = {
    AppointmentStatus.pending.value,
    AppointmentStatus.awaiting_confirmation.value,
    AppointmentStatus.rescheduled.value,
}
MANUAL_CONFIRM_REASON_PREFIX = "CHECKIN_CENTER_MANUAL_CONFIRM previous_status="
MANUAL_CONFIRM_NOTIFICATION_KEYS: tuple[str, ...] = (
    "appointment_checkin_center_confirmed",
    "appointment_checkin_center_confirmed_email",
)

OPERATIONAL_NOTIFICATION_KEYS = {
    AppointmentStatus.checked_in.value: (
        "appointment_checked_in",
        "appointment_checked_in_email",
    ),
    AppointmentStatus.in_progress.value: (
        "appointment_in_progress",
        "appointment_in_progress_email",
    ),
    AppointmentStatus.completed.value: (
        "appointment_completed",
        "appointment_completed_email",
    ),
    AppointmentStatus.cancelled.value: (
        "appointment_cancelled",
        "appointment_cancelled_email",
    ),
    AppointmentStatus.no_show.value: (
        "appointment_no_show",
        "appointment_no_show_email",
    ),
}


def _public_base_url(context: TenantContext) -> str:
    scheme = "http" if context.hostname in {"localhost", "127.0.0.1"} else "https"
    return f"{scheme}://{context.hostname}"


def _undo_target(current_status: str, *, simplified: bool) -> str | None:
    if current_status == AppointmentStatus.checked_in.value:
        return AppointmentStatus.confirmed.value
    if current_status == AppointmentStatus.in_progress.value:
        return AppointmentStatus.checked_in.value
    if current_status == AppointmentStatus.completed.value:
        return (
            AppointmentStatus.confirmed.value
            if simplified
            else AppointmentStatus.in_progress.value
        )
    if current_status in {
        AppointmentStatus.cancelled.value,
        AppointmentStatus.no_show.value,
    }:
        return AppointmentStatus.confirmed.value
    return None


async def _manual_confirmation_previous_status(
    session: AsyncSession,
    appointment_id: str,
) -> str | None:
    # A confirmação manual só é reversível enquanto ela for a confirmação
    # CONFIRMED mais recente. Se o cliente (ou outro fluxo) confirmar depois,
    # essa confirmação mais nova passa a ser soberana e invalida o undo manual.
    reason = await session.scalar(
        text(
            """
            select reason
            from appointment_status_history
            where appointment_id=cast(:appointment_id as uuid)
              and status=:confirmed
            order by created_at desc
            limit 1
            """
        ),
        {
            "appointment_id": appointment_id,
            "confirmed": AppointmentStatus.confirmed.value,
        },
    )
    if not reason:
        return None
    value = str(reason)
    if not value.startswith(MANUAL_CONFIRM_REASON_PREFIX):
        return None
    previous_status = value.removeprefix(MANUAL_CONFIRM_REASON_PREFIX).strip().upper()
    return previous_status if previous_status in MANUAL_CONFIRMABLE_STATUSES else None


async def _publish_realtime(
    context: TenantContext,
    session: AsyncSession,
    appointment_id: str,
    *,
    event_type: str,
    extra: dict[str, Any] | None = None,
) -> None:
    event = await RealtimeEventService(session).emit_appointment(
        appointment_id,
        event_type,
        actor="tenant-check-in-center",
        extra={"source": "check-in-center", **(extra or {})},
    )
    event_id = str(event.get("id") or "") if event else ""
    if event_id:
        celery_app.send_task(
            "app.workers.tasks.dispatch_realtime_push",
            args=[context.tenant_id, event_id],
            queue="notifications",
        )


async def _schedule_manual_confirmation_notification(
    session: AsyncSession,
    appointment_id: str,
    *,
    public_base_url: str,
) -> None:
    notifications = NotificationService(session, public_base_url=public_base_url)
    context = await notifications._appointment_context(appointment_id)
    if not context:
        return

    service_line = (
        f"Serviço: {context['service_name']}\n" if context.get("service_name") else ""
    )
    message = (
        f"Olá, {context.get('customer_name') or 'cliente'}!\n\n"
        "Seu atendimento foi confirmado manualmente pela equipe.\n"
        f"{service_line}"
        f"Profissional: {context.get('professional_name') or 'Agenda geral'}\n"
        f"Data/Horário: {context.get('starts_at_br') or ''}.\n\n"
        "Se precisar de qualquer ajuste, entre em contato com o estabelecimento."
    ).strip()
    payload: dict[str, Any] = {
        **context,
        "message": message,
        "manual_confirmation": True,
    }
    scheduled_at = datetime.now(UTC)

    phone = str(context.get("customer_phone") or "").strip()
    if phone:
        await notifications._enqueue(
            appointment_id=appointment_id,
            template_key=MANUAL_CONFIRM_NOTIFICATION_KEYS[0],
            channel="whatsapp",
            recipient=phone,
            payload=payload,
            scheduled_at=scheduled_at,
        )

    email = str(context.get("customer_email") or "").strip()
    if email and await notifications._email_enabled():
        await notifications._enqueue(
            appointment_id=appointment_id,
            template_key=MANUAL_CONFIRM_NOTIFICATION_KEYS[1],
            channel="email",
            recipient=email,
            payload={**payload, "subject": "Atendimento confirmado — Scheduler Pro"},
            scheduled_at=scheduled_at,
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


async def _cancel_pending_notifications(
    session: AsyncSession,
    appointment_id: str,
    template_keys: tuple[str, ...],
) -> tuple[int, int]:
    if not template_keys:
        return 0, 0
    sent = int(
        await session.scalar(
            text(
                """
                select count(*)
                from notification_jobs
                where appointment_id=cast(:appointment_id as uuid)
                  and template_key=any(:template_keys)
                  and status='SENT'
                """
            ),
            {
                "appointment_id": appointment_id,
                "template_keys": list(template_keys),
            },
        )
        or 0
    )
    result = await session.execute(
        text(
            """
            update notification_jobs
            set status='CANCELLED',
                error='Etapa operacional desfeita antes do envio.'
            where appointment_id=cast(:appointment_id as uuid)
              and template_key=any(:template_keys)
              and status='PENDING'
            """
        ),
        {
            "appointment_id": appointment_id,
            "template_keys": list(template_keys),
        },
    )
    return int(getattr(result, "rowcount", 0) or 0), sent


@router.get("/{appointment_id}/undo-state")
async def get_undo_state(
    appointment_id: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    parameters = await BookingParametersService(session).get()
    simplified = parameters.get("checkin_flow_mode") == "SIMPLE"
    service = AppointmentService(session)
    current = await service.get(appointment_id)
    current_status = str(current.get("status") or "").upper()
    target_status = _undo_target(current_status, simplified=simplified)
    if current_status == AppointmentStatus.confirmed.value:
        target_status = await _manual_confirmation_previous_status(session, appointment_id)
    return success(
        {
            "reversible": target_status is not None,
            "from_status": current_status,
            "to_status": target_status,
        }
    )


@router.post("/{appointment_id}/confirm")
async def confirm_from_checkin_center(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Confirma manualmente no Check-in preservando origem para eventual desfazer."""
    service = AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    )
    current = await service.get(appointment_id)
    current_status = str(current.get("status") or "").upper()
    if current_status == AppointmentStatus.confirmed.value:
        return success(current)
    if current_status not in MANUAL_CONFIRMABLE_STATUSES:
        raise APIError(
            "CHECKIN_MANUAL_CONFIRM_NOT_ALLOWED",
            "Este atendimento não está aguardando confirmação manual.",
            409,
            {"current_status": current_status},
        )

    result = await session.execute(
        text(
            """
            update appointments
            set status=:confirmed
            where id=cast(:appointment_id as uuid)
              and status=:current_status
            """
        ),
        {
            "appointment_id": appointment_id,
            "confirmed": AppointmentStatus.confirmed.value,
            "current_status": current_status,
        },
    )
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        raise APIError(
            "CHECKIN_CONFIRMATION_CHANGED",
            "O atendimento foi alterado por outro operador. Atualize a Central de Check-in.",
            409,
        )
    await service._add_history(
        appointment_id,
        AppointmentStatus.confirmed.value,
        f"{MANUAL_CONFIRM_REASON_PREFIX}{current_status}",
    )
    await _schedule_manual_confirmation_notification(
        session,
        appointment_id,
        public_base_url=_public_base_url(context),
    )
    await session.commit()
    await _publish_realtime(
        context,
        session,
        appointment_id,
        event_type="appointment.confirmed",
        extra={
            "manual_confirmation": True,
            "previous_status": current_status,
        },
    )
    return success(await service.get(appointment_id))


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
        event_type="appointment.checked_in",
        extra={"completed_by_checkin": simplified},
    )
    return success(await service.get(appointment_id))


@router.post("/{appointment_id}/undo")
async def undo_check_in_stage(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Recua exatamente uma etapa operacional do atendimento."""
    parameters = await BookingParametersService(session).get()
    simplified = parameters.get("checkin_flow_mode") == "SIMPLE"
    service = AppointmentService(
        session,
        public_base_url=_public_base_url(context),
    )
    current = await service.get(appointment_id)
    current_status = str(current.get("status") or "").upper()
    target_status = _undo_target(current_status, simplified=simplified)
    keys: tuple[str, ...] = OPERATIONAL_NOTIFICATION_KEYS.get(current_status, ())

    if current_status == AppointmentStatus.confirmed.value:
        target_status = await _manual_confirmation_previous_status(session, appointment_id)
        keys = MANUAL_CONFIRM_NOTIFICATION_KEYS if target_status is not None else ()

    if target_status is None:
        raise APIError(
            "CHECKIN_STAGE_NOT_REVERSIBLE",
            "Não existe uma etapa operacional anterior para desfazer.",
            409,
            {"current_status": current_status},
        )

    if simplified and current_status == AppointmentStatus.completed.value:
        keys = (
            "appointment_checked_in",
            "appointment_checked_in_email",
            "appointment_completed",
            "appointment_completed_email",
        )
    cancelled_notifications, already_sent = await _cancel_pending_notifications(
        session,
        appointment_id,
        keys,
    )
    result = await session.execute(
        text(
            """
            update appointments
            set status=:target_status
            where id=cast(:appointment_id as uuid)
              and status=:current_status
            """
        ),
        {
            "appointment_id": appointment_id,
            "current_status": current_status,
            "target_status": target_status,
        },
    )
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        raise APIError(
            "CHECKIN_STAGE_CHANGED",
            "O atendimento foi alterado por outro operador. Atualize a Central de Check-in.",
            409,
        )
    await service._add_history(
        appointment_id,
        target_status,
        f"Etapa {current_status} desfeita pela Central de Check-in",
    )
    await session.commit()
    await _publish_realtime(
        context,
        session,
        appointment_id,
        event_type="appointment.status_reverted",
        extra={
            "from_status": current_status,
            "to_status": target_status,
            "notifications_cancelled": cancelled_notifications,
            "notifications_already_sent": already_sent,
        },
    )
    return success(
        {
            "appointment": await service.get(appointment_id),
            "from_status": current_status,
            "to_status": target_status,
            "notifications_cancelled": cancelled_notifications,
            "notifications_already_sent": already_sent,
        }
    )