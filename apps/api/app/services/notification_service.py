import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.whatsapp_provider import WhatsAppProviderFactory


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _row(row: RowMapping) -> dict[str, Any]:
        return dict(row)

    async def schedule_for_appointment(self, appointment_id: str, event_name: str) -> None:
        row = (
            await self.session.execute(
                text(
                    """
                    select a.id::text, a.starts_at, a.status,
                           c.name as customer_name, c.phone as customer_phone,
                           s.name as service_name,
                           p.name as professional_name
                    from appointments a
                    join customers c on c.id = a.customer_id
                    join services s on s.id = a.service_id
                    join professionals p on p.id = a.professional_id
                    where a.id = :appointment_id::uuid
                    """
                ),
                {"appointment_id": appointment_id},
            )
        ).mappings().first()
        if row is None or not row.get("customer_phone"):
            return
        send_at = datetime.now(UTC)
        if event_name == "appointment_confirmed":
            send_at = max(datetime.now(UTC), row["starts_at"] - timedelta(hours=24))
        message = (
            f"Olá, {row['customer_name']}! Seu agendamento de {row['service_name']} "
            f"com {row['professional_name']} está com status {row['status']} em "
            f"{row['starts_at']:%d/%m/%Y %H:%M}."
        )
        await self.session.execute(
            text(
                """
                insert into notification_jobs(
                    appointment_id, channel, recipient, template_key, payload, scheduled_at, status
                ) values(
                    :appointment_id::uuid, 'whatsapp', :recipient, :template_key,
                    cast(:payload as jsonb), :scheduled_at, 'PENDING'
                )
                """
            ),
            {
                "appointment_id": appointment_id,
                "recipient": row["customer_phone"],
                "template_key": event_name,
                "payload": json.dumps({"message": message}, ensure_ascii=False),
                "scheduled_at": send_at,
            },
        )

    async def list_jobs(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        where = "where status=:status" if status else ""
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select id::text, appointment_id::text, channel, recipient, template_key,
                           payload, scheduled_at, sent_at, status, error
                    from notification_jobs
                    {where}
                    order by scheduled_at desc
                    limit :limit
                    """
                ),
                params,
            )
        ).mappings().all()
        return [self._row(row) for row in rows]

    async def process_due(self, *, limit: int = 50) -> dict[str, Any]:
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
                {"limit": limit},
            )
        ).mappings().all()
        sent = 0
        failed = 0
        provider = WhatsAppProviderFactory.make()
        for row in rows:
            message = str((row["payload"] or {}).get("message", ""))
            try:
                await provider.send_text(str(row["recipient"]), message)
                await self.session.execute(
                    text("update notification_jobs set status='SENT', sent_at=now(), error=null where id=:id::uuid"),
                    {"id": row["id"]},
                )
                sent += 1
            except Exception as exc:
                await self.session.execute(
                    text("update notification_jobs set status='FAILED', error=:error where id=:id::uuid"),
                    {"id": row["id"], "error": str(exc)[:1000]},
                )
                failed += 1
        await self.session.commit()
        return {"sent": sent, "failed": failed, "total": len(rows)}
