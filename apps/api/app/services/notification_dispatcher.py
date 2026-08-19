from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.appointment_confirmation_service import AppointmentConfirmationService
from app.services.notification_service import NotificationService
from app.services.tenant_event_log import record_tenant_event
from app.services.tenant_mail_service import TenantMailService
from app.services.whatsapp_provider import WhatsAppProviderFactory


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

    async def process_due(self, *, limit: int = 100) -> dict[str, Any]:
        confirmation = await AppointmentConfirmationService(self.session).expire_due(
            limit=min(max(limit, 1), 500)
        )

        rows = (
            await self.session.execute(
                text(
                    """
                    select id::text, channel, recipient, template_key, payload
                    from notification_jobs
                    where status='PENDING' and scheduled_at <= now()
                    order by scheduled_at asc
                    limit :limit
                    for update skip locked
                    """
                ),
                {"limit": min(max(limit, 1), 500)},
            )
        ).mappings().all()
        instance_name = await self._instance_name()
        whatsapp_provider = WhatsAppProviderFactory.make(instance_name)
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
                    await whatsapp_provider.send_text(str(row["recipient"]), message)
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
            "confirmations_expired": confirmation["expired"],
            "confirmation_expiry_failures": confirmation["failed"],
        }
