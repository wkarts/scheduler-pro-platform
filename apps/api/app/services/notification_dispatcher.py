from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.appointment_confirmation_service import AppointmentConfirmationService
from app.services.notification_service import NotificationService
from app.services.phone_normalization import PhoneNormalizationService
from app.services.tenant_event_log import record_tenant_event
from app.services.tenant_mail_service import TenantMailService
from app.services.whatsapp_provider import WhatsAppProviderFactory

OPERATIONAL_TEMPLATE_KEYS = (
    "appointment_checkin_center_confirmed",
    "appointment_checkin_center_confirmed_email",
    "appointment_checked_in",
    "appointment_checked_in_email",
    "appointment_in_progress",
    "appointment_in_progress_email",
    "appointment_completed",
    "appointment_completed_email",
    "appointment_cancelled",
    "appointment_cancelled_email",
    "appointment_no_show",
    "appointment_no_show_email",
)


def _recipient_hint(value: str, channel: str) -> str:
    clean = value.strip()
    if not clean:
        return "não informado"
    if channel == "email" and "@" in clean:
        local, domain = clean.split("@", 1)
        return f"{local[:1]}***@{domain}"
    digits = "".join(character for character in clean if character.isdigit())
    return f"***{digits[-4:]}" if digits else "***"


class TenantNotificationDispatcher:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _instance_name(self) -> str | None:
        value = await self.session.scalar(
            text(
                "select instance_name from whatsapp_integrations "
                "where name='default' limit 1"
            )
        )
        return str(value) if value else None

    async def _operational_delay_seconds(self) -> int:
        value = await self.session.scalar(
            text(
                "select value from tenant_settings "
                "where key='checkin_notification_delay_seconds' limit 1"
            )
        )
        try:
            parsed = int(value if value is not None else 120)
        except (TypeError, ValueError):
            parsed = 120
        return max(0, min(600, parsed))

    async def process_due(self, *, limit: int = 100) -> dict[str, Any]:
        confirmation = await AppointmentConfirmationService(self.session).expire_due(
            limit=min(max(limit, 1), 500)
        )
        operational_delay = await self._operational_delay_seconds()
        operational_cutoff = datetime.now(UTC) - timedelta(seconds=operational_delay)

        rows = (
            await self.session.execute(
                text(
                    """
                    select id::text, channel, recipient, template_key, payload
                    from notification_jobs
                    where status='PENDING'
                      and scheduled_at <= now()
                      and (
                        not (template_key = any(:operational_templates))
                        or scheduled_at <= :operational_cutoff
                      )
                    order by scheduled_at asc
                    limit :limit
                    for update skip locked
                    """
                ),
                {
                    "limit": min(max(limit, 1), 500),
                    "operational_templates": list(OPERATIONAL_TEMPLATE_KEYS),
                    "operational_cutoff": operational_cutoff,
                },
            )
        ).mappings().all()
        instance_name = await self._instance_name()
        whatsapp_provider = WhatsAppProviderFactory.make(instance_name)
        phone_service = await PhoneNormalizationService.from_session(self.session)
        mailer = TenantMailService(self.session)
        sent = 0
        failed = 0
        for row in rows:
            payload = NotificationService._normalize_payload(row["payload"])
            message = str(payload.get("message") or "").strip()
            channel = str(row["channel"] or "whatsapp").lower()
            recipient_hint = _recipient_hint(str(row["recipient"] or ""), channel)
            template_key = str(row["template_key"] or "")
            if not message:
                await self.session.execute(
                    text(
                        "update notification_jobs set status='FAILED', "
                        "error='Mensagem vazia' where id=cast(:id as uuid)"
                    ),
                    {"id": row["id"]},
                )
                await record_tenant_event(
                    self.session,
                    source="notification",
                    service="notification-dispatcher",
                    level="ERROR",
                    event="notification_failed",
                    message="Notificação não enviada porque a mensagem estava vazia.",
                    integration=channel,
                    error_code="NOTIFICATION_EMPTY_MESSAGE",
                    details={
                        "job_id": row["id"],
                        "template_key": template_key,
                        "recipient": recipient_hint,
                    },
                )
                failed += 1
                continue
            try:
                if channel == "email":
                    subject = str(
                        payload.get("subject")
                        or NotificationService.email_subject(template_key, payload)
                    )
                    await mailer.send(str(row["recipient"]), subject, message)
                elif channel == "whatsapp":
                    normalized_recipient = phone_service.normalize(
                        str(row["recipient"] or ""),
                        required=True,
                    )
                    assert normalized_recipient is not None
                    await whatsapp_provider.send_text(normalized_recipient, message)
                else:
                    raise RuntimeError(f"Canal de notificação não suportado: {channel}")
                await self.session.execute(
                    text(
                        "update notification_jobs set status='SENT', "
                        "sent_at=now(), error=null where id=cast(:id as uuid)"
                    ),
                    {"id": row["id"]},
                )
                await record_tenant_event(
                    self.session,
                    source="notification",
                    service="notification-dispatcher",
                    event="notification_sent",
                    message=f"Notificação {channel} enviada com sucesso.",
                    integration=channel,
                    details={
                        "job_id": row["id"],
                        "template_key": template_key,
                        "recipient": recipient_hint,
                    },
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001 - job failure must be persisted
                error_text = str(exc)[:1000]
                await self.session.execute(
                    text(
                        "update notification_jobs set status='FAILED', "
                        "error=:error where id=cast(:id as uuid)"
                    ),
                    {"id": row["id"], "error": error_text},
                )
                await record_tenant_event(
                    self.session,
                    source="notification",
                    service="notification-dispatcher",
                    level="ERROR",
                    event="notification_failed",
                    message=f"Falha ao enviar notificação pelo canal {channel}.",
                    integration=channel,
                    error_code=type(exc).__name__,
                    details={
                        "job_id": row["id"],
                        "template_key": template_key,
                        "recipient": recipient_hint,
                        "error": error_text,
                    },
                )
                failed += 1
        await self.session.commit()
        return {
            "sent": sent,
            "failed": failed,
            "total": len(rows),
            "instance_name": instance_name,
            "operational_delay_seconds": operational_delay,
            "confirmations_expired": confirmation["expired"],
            "confirmation_expiry_failures": confirmation["failed"],
        }
