from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.appointment_confirmation_service import AppointmentConfirmationService
from app.services.notification_service import NotificationService
from app.services.whatsapp_provider import WhatsAppProviderFactory


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
        # O sweep já roda para cada tenant a cada minuto. Antes de enviar os jobs,
        # encerra reservas que ultrapassaram o prazo de confirmação. O cancelamento
        # muda o status para CANCELLED, portanto o motor de disponibilidade libera
        # o slot imediatamente sem outro processo auxiliar.
        confirmation = await AppointmentConfirmationService(self.session).expire_due(
            limit=min(max(limit, 1), 500)
        )

        rows = (
            await self.session.execute(
                text(
                    """
                    select id::text, recipient, payload
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
        provider = WhatsAppProviderFactory.make(instance_name)
        sent = 0
        failed = 0
        for row in rows:
            payload = NotificationService._normalize_payload(row["payload"])
            message = str(payload.get("message") or "").strip()
            if not message:
                await self.session.execute(
                    text(
                        "update notification_jobs set status='FAILED', "
                        "error='Mensagem vazia' where id=cast(:id as uuid)"
                    ),
                    {"id": row["id"]},
                )
                failed += 1
                continue
            try:
                await provider.send_text(str(row["recipient"]), message)
                await self.session.execute(
                    text(
                        "update notification_jobs set status='SENT', "
                        "sent_at=now(), error=null where id=cast(:id as uuid)"
                    ),
                    {"id": row["id"]},
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001 - job failure must be persisted
                await self.session.execute(
                    text(
                        "update notification_jobs set status='FAILED', "
                        "error=:error where id=cast(:id as uuid)"
                    ),
                    {"id": row["id"], "error": str(exc)[:1000]},
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
