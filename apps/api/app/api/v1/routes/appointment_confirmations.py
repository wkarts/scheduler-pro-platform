import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.enums import AppointmentStatus
from app.core.errors import APIError
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.appointment_confirmation_service import AppointmentConfirmationService
from app.services.appointment_service import AppointmentService
from app.services.notification_service import NotificationService
from app.services.tenant_event_log import record_tenant_event

router = APIRouter()

WAITING_CONFIRMATION_STATUSES = {
    AppointmentStatus.pending.value,
    AppointmentStatus.awaiting_confirmation.value,
    AppointmentStatus.rescheduled.value,
}
AUTO_EXPIRY_REASON_PREFIX = "Prazo de confirmação expirado"
CLIENT_CONFIRM_REASON_PREFIX = "Confirmado pelo cliente através do link público"
CLIENT_CANCEL_REASON_PREFIX = "Cancelado pelo cliente através do link público"
MANUAL_CONFIRM_REASON_PREFIX = "CHECKIN_CENTER_MANUAL_CONFIRM previous_status="
CONFIRMATION_MESSAGE_KEYS = (
    "appointment_confirmation_request",
    "appointment_confirmation_request_email",
    "appointment_confirmation_resend",
    "appointment_confirmation_resend_email",
    "appointment_confirmation_renewed",
    "appointment_confirmation_renewed_email",
)


def _public_base_url(context: TenantContext) -> str:
    scheme = "http" if context.hostname in {"localhost", "127.0.0.1"} else "https"
    return f"{scheme}://{context.hostname}"


def _is_expired(value: Any, now: datetime) -> bool:
    return isinstance(value, datetime) and value <= now


def _status_payload(row: RowMapping) -> dict[str, Any]:
    now = datetime.now(UTC)
    appointment_status = str(row["appointment_status"] or "").upper()
    request_state = str(row["request_state"] or "").upper() or None
    has_request = bool(row["request_id"])
    deadline_expired = _is_expired(row["confirmation_deadline"], now)
    link_expired = _is_expired(row["expires_at"], now)
    last_confirm_reason = str(row["last_confirm_reason"] or "")
    last_reason = str(row["last_reason"] or "")

    customer_confirmed = (
        appointment_status == AppointmentStatus.confirmed.value
        and last_confirm_reason.startswith(CLIENT_CONFIRM_REASON_PREFIX)
    )
    manual_confirmed = (
        appointment_status == AppointmentStatus.confirmed.value
        and last_confirm_reason.startswith(MANUAL_CONFIRM_REASON_PREFIX)
    )
    cancelled_by_client = (
        appointment_status == AppointmentStatus.cancelled.value
        and last_reason.startswith(CLIENT_CANCEL_REASON_PREFIX)
    )
    auto_expired_cancel = (
        appointment_status == AppointmentStatus.cancelled.value
        and last_reason.startswith(AUTO_EXPIRY_REASON_PREFIX)
    )

    waiting = appointment_status in WAITING_CONFIRMATION_STATUSES
    valid_pending_request = (
        has_request
        and request_state == "PENDING"
        and not deadline_expired
        and not link_expired
    )
    can_send = waiting and not has_request
    can_resend = waiting and valid_pending_request
    can_renew = (
        waiting
        and has_request
        and (
            request_state in {"EXPIRED", "REVOKED"}
            or deadline_expired
            or link_expired
        )
    ) or auto_expired_cancel

    action: str | None = None
    label = appointment_status.replace("_", " ").title()
    source: str | None = None
    if can_renew:
        action = "renew"
        label = "Prazo de confirmação vencido"
    elif can_resend:
        action = "resend"
        label = "Aguardando confirmação"
    elif can_send:
        action = "send"
        label = "Confirmação ainda não enviada"
    elif customer_confirmed:
        label = "Confirmado pelo cliente"
        source = "client"
    elif manual_confirmed:
        label = "Confirmado manualmente"
        source = "operator"
    elif cancelled_by_client:
        label = "Cancelado pelo cliente"
        source = "client"
    elif auto_expired_cancel:
        label = "Prazo vencido — horário liberado"
        source = "system"
    elif appointment_status == AppointmentStatus.cancelled.value:
        label = "Cancelado"
        source = "operator_or_system"
    elif waiting:
        label = "Aguardando confirmação"

    return {
        "appointment_id": str(row["appointment_id"]),
        "appointment_status": appointment_status,
        "request_state": request_state,
        "has_request": has_request,
        "confirmation_deadline": row["confirmation_deadline"],
        "expires_at": row["expires_at"],
        "deadline_expired": deadline_expired,
        "link_expired": link_expired,
        "can_send": can_send,
        "can_resend": can_resend,
        "can_renew": can_renew,
        "action": action,
        "label": label,
        "source": source,
        "customer_confirmed": customer_confirmed,
        "manual_confirmed": manual_confirmed,
        "auto_expired_cancel": auto_expired_cancel,
    }


async def _confirmation_rows(
    session: AsyncSession,
    appointment_ids: list[str],
) -> list[RowMapping]:
    if not appointment_ids:
        return []
    rows = (
        await session.execute(
            text(
                """
                select a.id::text as appointment_id,
                       a.status as appointment_status,
                       a.starts_at,
                       a.ends_at,
                       a.professional_id::text as professional_id,
                       a.source,
                       acr.id::text as request_id,
                       acr.state as request_state,
                       acr.confirmation_deadline,
                       acr.expires_at,
                       acr.responded_at,
                       (
                         select h.reason
                         from appointment_status_history h
                         where h.appointment_id=a.id and h.status='CONFIRMED'
                         order by h.created_at desc
                         limit 1
                       ) as last_confirm_reason,
                       (
                         select h.reason
                         from appointment_status_history h
                         where h.appointment_id=a.id
                         order by h.created_at desc
                         limit 1
                       ) as last_reason
                from appointments a
                left join appointment_confirmation_requests acr
                  on acr.appointment_id=a.id
                where a.id::text = any(:appointment_ids)
                """
            ),
            {"appointment_ids": appointment_ids},
        )
    ).mappings().all()
    return list(rows)


async def _confirmation_row(
    session: AsyncSession,
    appointment_id: str,
) -> RowMapping:
    rows = await _confirmation_rows(session, [appointment_id])
    if not rows:
        raise APIError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.", 404)
    return rows[0]


async def _cancel_pending_confirmation_messages(
    session: AsyncSession,
    appointment_id: str,
) -> None:
    await session.execute(
        text(
            """
            update notification_jobs
            set status='CANCELLED',
                error='Substituída por envio manual mais recente do link de confirmação.'
            where appointment_id=cast(:appointment_id as uuid)
              and template_key=any(:template_keys)
              and status='PENDING'
            """
        ),
        {
            "appointment_id": appointment_id,
            "template_keys": list(CONFIRMATION_MESSAGE_KEYS),
        },
    )


async def _queue_confirmation_delivery(
    session: AsyncSession,
    appointment_id: str,
    *,
    request: dict[str, Any],
    template_base: str,
    public_base_url: str,
) -> list[str]:
    notifications = NotificationService(session, public_base_url=public_base_url)
    context = await notifications._appointment_context(appointment_id)
    if context is None:
        raise APIError("APPOINTMENT_NOT_FOUND", "Agendamento não encontrado.", 404)

    context.update(
        {
            "confirmation_url": request["url"],
            "confirmation_deadline": request["confirmation_deadline"],
            "confirmation_expires_at": request["expires_at"],
        }
    )
    channels: list[str] = []
    phone = str(context.get("customer_phone") or "").strip()
    email = str(context.get("customer_email") or "").strip()
    email_enabled = bool(email) and await notifications._email_enabled()

    async def enqueue(channel: str, recipient: str) -> None:
        template_key = template_base if channel == "whatsapp" else f"{template_base}_email"
        body = await notifications._template_body(template_key, channel)
        message = notifications._render(body, context)
        payload: dict[str, Any] = {**context, "message": message}
        if channel == "email":
            payload["subject"] = await notifications._template_subject(template_key, context)
        await session.execute(
            text(
                """
                insert into notification_jobs(
                    appointment_id, channel, recipient, template_key,
                    payload, scheduled_at, sent_at, status, error
                ) values(
                    cast(:appointment_id as uuid), :channel, :recipient, :template_key,
                    cast(:payload as jsonb), now(), null, 'PENDING', null
                )
                on conflict (appointment_id, channel, template_key)
                where appointment_id is not null
                do update set
                    recipient=excluded.recipient,
                    payload=excluded.payload,
                    scheduled_at=now(),
                    sent_at=null,
                    status='PENDING',
                    error=null
                """
            ),
            {
                "appointment_id": appointment_id,
                "channel": channel,
                "recipient": recipient,
                "template_key": template_key,
                "payload": json.dumps(payload, ensure_ascii=False, default=str),
            },
        )
        channels.append(channel)

    if phone:
        await enqueue("whatsapp", phone)
    if email_enabled:
        await enqueue("email", email)
    if not channels:
        raise APIError(
            "CONFIRMATION_RECIPIENT_MISSING",
            "O cliente não possui WhatsApp/telefone utilizável nem e-mail habilitado para receber a confirmação.",
            409,
        )
    return channels


@router.post("/statuses")
async def confirmation_statuses(
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    raw_ids = payload.get("appointment_ids")
    if not isinstance(raw_ids, list):
        raise APIError(
            "CONFIRMATION_STATUS_IDS_REQUIRED",
            "Informe appointment_ids para consultar as confirmações.",
            422,
        )
    appointment_ids = [str(value).strip() for value in raw_ids if str(value).strip()]
    appointment_ids = list(dict.fromkeys(appointment_ids))
    if len(appointment_ids) > 200:
        raise APIError(
            "CONFIRMATION_STATUS_TOO_MANY_IDS",
            "Consulte no máximo 200 agendamentos por vez.",
            422,
        )
    rows = await _confirmation_rows(session, appointment_ids)
    return success({str(row["appointment_id"]): _status_payload(row) for row in rows})


@router.get("/{appointment_id}")
async def confirmation_link(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = AppointmentConfirmationService(session)
    request = await service.ensure_request(
        appointment_id,
        public_base_url=_public_base_url(context),
    )
    await session.commit()
    return success(
        {
            "enabled": request is not None,
            "request": request,
            "preferences": await service.notification_preferences(),
        }
    )


@router.post("/{appointment_id}/send")
async def send_confirmation_link(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Envia, reenvia ou renova a confirmação sem alterar fluxos já confirmados."""
    await session.execute(
        text("select pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"appointment-confirmation-operator:{appointment_id}"},
    )
    row = await _confirmation_row(session, appointment_id)
    status = _status_payload(row)
    action = str(status.get("action") or "")
    if action not in {"send", "resend", "renew"}:
        raise APIError(
            "CONFIRMATION_MANUAL_SEND_NOT_ALLOWED",
            "Este atendimento não está elegível para envio ou renovação da confirmação.",
            409,
            {
                "appointment_status": status["appointment_status"],
                "request_state": status["request_state"],
                "label": status["label"],
            },
        )

    public_base_url = _public_base_url(context)
    appointment_service = AppointmentService(
        session,
        public_base_url=public_base_url,
    )
    confirmation_service = AppointmentConfirmationService(session)

    try:
        if action == "renew" and bool(status.get("auto_expired_cancel")):
            starts_at = row["starts_at"]
            ends_at = row["ends_at"]
            if not isinstance(starts_at, datetime) or not isinstance(ends_at, datetime):
                raise APIError(
                    "APPOINTMENT_INTERVAL_INVALID",
                    "O horário original do atendimento está inválido e não pode ser reaberto.",
                    409,
                )
            await appointment_service._ensure_slot_available(
                str(row["professional_id"]),
                starts_at,
                ends_at,
                source=str(row["source"] or "internal"),
                ignore_appointment_id=appointment_id,
            )
            result = await session.execute(
                text(
                    """
                    update appointments
                    set status=:status
                    where id=cast(:appointment_id as uuid)
                      and status='CANCELLED'
                    """
                ),
                {
                    "appointment_id": appointment_id,
                    "status": AppointmentStatus.awaiting_confirmation.value,
                },
            )
            if int(getattr(result, "rowcount", 0) or 0) != 1:
                raise APIError(
                    "CONFIRMATION_RENEW_STATE_CHANGED",
                    "O atendimento foi alterado por outro operador. Atualize a Central de Check-in.",
                    409,
                )
            await appointment_service._add_history(
                appointment_id,
                AppointmentStatus.awaiting_confirmation.value,
                "Prazo de confirmação renovado manualmente; horário reaberto após expiração automática",
            )

        rotate = action == "renew"
        request = await confirmation_service.ensure_request(
            appointment_id,
            public_base_url=public_base_url,
            rotate=rotate,
        )
        if request is None:
            raise APIError(
                "CONFIRMATION_DISABLED",
                "A confirmação de agendamentos está desativada neste tenant.",
                409,
            )

        await _cancel_pending_confirmation_messages(session, appointment_id)
        if action == "renew":
            template_base = "appointment_confirmation_renewed"
        elif action == "resend":
            template_base = "appointment_confirmation_resend"
        else:
            template_base = "appointment_confirmation_request"
        channels = await _queue_confirmation_delivery(
            session,
            appointment_id,
            request=request,
            template_base=template_base,
            public_base_url=public_base_url,
        )
        await record_tenant_event(
            session,
            source="appointment",
            service="confirmation-assistant",
            event=f"confirmation_link_{action}",
            message=(
                "Prazo de confirmação renovado e mensagem reenviada manualmente."
                if action == "renew"
                else "Link de confirmação enviado manualmente ao cliente."
            ),
            integration="confirmation",
            details={
                "appointment_id": appointment_id,
                "action": action,
                "channels": channels,
                "confirmation_deadline": str(request["confirmation_deadline"]),
                "expires_at": str(request["expires_at"]),
                # Nunca registrar URL/token de confirmação em logs ou auditoria.
            },
        )
        await session.commit()
    except Exception:
        await session.rollback()
        raise

    refreshed = await _confirmation_row(session, appointment_id)
    return success(
        {
            "action": action,
            "queued_channels": channels,
            "status": _status_payload(refreshed),
        }
    )


@router.post("/{appointment_id}/regenerate")
async def regenerate_confirmation_link(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = AppointmentConfirmationService(session)
    request = await service.ensure_request(
        appointment_id,
        public_base_url=_public_base_url(context),
        rotate=True,
    )
    await session.commit()
    return success({"enabled": request is not None, "request": request})
