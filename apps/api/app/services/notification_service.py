import json
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.whatsapp_provider import WhatsAppProviderFactory

DEFAULT_TEMPLATES = {
    "appointment_created": "Olá, {{customer_name}}! Seu atendimento de {{service_name}} com {{professional_name}} foi reservado para {{starts_at_br}}.",
    "appointment_confirmation_request": "Olá, {{customer_name}}! Seu atendimento de {{service_name}} com {{professional_name}} está reservado para {{starts_at_br}}. Confirme ou cancele pelo link: {{confirmation_url}}",
    "appointment_confirmed": "Olá, {{customer_name}}! Seu agendamento de {{service_name}} com {{professional_name}} foi confirmado para {{starts_at_br}}.",
    "appointment_cancelled": "Olá, {{customer_name}}. Seu agendamento de {{service_name}} para {{starts_at_br}} foi cancelado. Motivo: {{reason}}",
    "appointment_completed": "Olá, {{customer_name}}! Obrigado por realizar {{service_name}} com a gente. Até a próxima!",
    "appointment_no_show": "Olá, {{customer_name}}. Registramos ausência no agendamento de {{service_name}} previsto para {{starts_at_br}}.",
    "appointment_reminder_24h": "Lembrete: {{customer_name}}, seu atendimento de {{service_name}} com {{professional_name}} é amanhã, {{starts_at_br}}.",
    "appointment_reminder_2h": "Lembrete: {{customer_name}}, faltam 2 horas para seu atendimento de {{service_name}} com {{professional_name}} às {{starts_at_br}}.",
    "tenant_confirmation_confirmed": "✅ {{customer_name}} confirmou o agendamento de {{service_name}} para {{starts_at_br}}.",
    "tenant_confirmation_cancelled": "❌ {{customer_name}} cancelou o agendamento de {{service_name}} para {{starts_at_br}}. O horário foi liberado.",
    "tenant_confirmation_expired": "⏱️ {{customer_name}} não confirmou o agendamento de {{service_name}} para {{starts_at_br}} dentro do prazo. O horário foi liberado.",
}


class NotificationService:
    def __init__(self, session: AsyncSession, *, public_base_url: str | None = None) -> None:
        self.session = session
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None

    @staticmethod
    def _row(row: RowMapping) -> dict[str, Any]:
        return dict(row)

    @staticmethod
    def _normalize_payload(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    @staticmethod
    def _render(body: str, variables: dict[str, Any]) -> str:
        rendered = body
        for key, value in variables.items():
            rendered = rendered.replace(
                "{{" + key + "}}",
                "" if value is None else str(value),
            )
        return rendered

    async def _setting(self, key: str, default: Any) -> Any:
        value = await self.session.scalar(
            text("select value from tenant_settings where key=:key limit 1"),
            {"key": key},
        )
        return default if value is None else value

    async def _timezone(self) -> ZoneInfo:
        context_timezone = str(
            self.session.info.get("tenant_timezone") or "America/Bahia"
        )
        name = str(
            await self._setting("timezone", context_timezone)
            or context_timezone
        )
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            try:
                return ZoneInfo(context_timezone)
            except ZoneInfoNotFoundError:
                return ZoneInfo("America/Bahia")

    async def _template_body(self, template_key: str, channel: str) -> str:
        body = await self.session.scalar(
            text(
                """
                select body
                from notification_templates
                where key=:template_key and channel=:channel and active=true
                limit 1
                """
            ),
            {"template_key": template_key, "channel": channel},
        )
        return str(body or DEFAULT_TEMPLATES.get(template_key) or "{{message}}")

    async def _appointment_context(
        self,
        appointment_id: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    select a.id::text, a.starts_at, a.ends_at, a.status,
                           c.name as customer_name, c.phone as customer_phone,
                           c.email as customer_email,
                           s.name as service_name, s.duration_minutes,
                           p.name as professional_name
                    from appointments a
                    join customers c on c.id = a.customer_id
                    join services s on s.id = a.service_id
                    join professionals p on p.id = a.professional_id
                    where a.id = cast(:appointment_id as uuid)
                    """
                ),
                {"appointment_id": appointment_id},
            )
        ).mappings().first()
        if row is None:
            return None

        timezone = await self._timezone()
        starts_at = row["starts_at"]
        ends_at = row["ends_at"]
        starts_at_br = (
            starts_at.astimezone(timezone).strftime("%d/%m/%Y %H:%M")
            if isinstance(starts_at, datetime)
            else ""
        )
        ends_at_br = (
            ends_at.astimezone(timezone).strftime("%d/%m/%Y %H:%M")
            if isinstance(ends_at, datetime)
            else ""
        )
        data = self._row(row)
        data.update(
            {
                "appointment_id": row["id"],
                "starts_at_iso": starts_at.isoformat() if isinstance(starts_at, datetime) else "",
                "ends_at_iso": ends_at.isoformat() if isinstance(ends_at, datetime) else "",
                "starts_at_br": starts_at_br,
                "ends_at_br": ends_at_br,
                "reason": reason or "não informado",
            }
        )
        return data

    @staticmethod
    def _scheduled_at_for(template_key: str, starts_at: datetime) -> datetime:
        now = datetime.now(UTC)
        if template_key == "appointment_reminder_24h":
            return max(now, starts_at - timedelta(hours=24))
        if template_key == "appointment_reminder_2h":
            return max(now, starts_at - timedelta(hours=2))
        return now

    @staticmethod
    def _templates_for_event(event_name: str) -> list[str]:
        if event_name == "appointment_confirmed":
            return [
                "appointment_confirmed",
                "appointment_reminder_24h",
                "appointment_reminder_2h",
            ]
        return [event_name]

    async def _enqueue(
        self,
        *,
        appointment_id: str,
        template_key: str,
        channel: str,
        recipient: str,
        payload: dict[str, Any],
        scheduled_at: datetime,
    ) -> None:
        await self.session.execute(
            text(
                """
                insert into notification_jobs(
                    appointment_id, channel, recipient, template_key,
                    payload, scheduled_at, status, error
                ) values(
                    cast(:appointment_id as uuid), :channel, :recipient, :template_key,
                    cast(:payload as jsonb), :scheduled_at, 'PENDING', null
                )
                on conflict (appointment_id, channel, template_key)
                where appointment_id is not null
                do update set
                    recipient = excluded.recipient,
                    payload = excluded.payload,
                    scheduled_at = excluded.scheduled_at,
                    status = case
                        when notification_jobs.status = 'SENT'
                        then notification_jobs.status
                        else 'PENDING'
                    end,
                    error = null
                """
            ),
            {
                "appointment_id": appointment_id,
                "channel": channel,
                "recipient": recipient,
                "template_key": template_key,
                "payload": json.dumps(payload, ensure_ascii=False, default=str),
                "scheduled_at": scheduled_at,
            },
        )

    async def schedule_for_appointment(
        self,
        appointment_id: str,
        event_name: str,
        *,
        reason: str | None = None,
        rotate_confirmation: bool = False,
    ) -> None:
        context = await self._appointment_context(appointment_id, reason=reason)
        if context is None or not context.get("customer_phone"):
            return

        if event_name in {"appointment_created", "appointment_rescheduled"}:
            from app.services.appointment_confirmation_service import (
                AppointmentConfirmationService,
            )

            confirmation_service = AppointmentConfirmationService(self.session)
            if await confirmation_service.confirmation_required():
                request = await confirmation_service.ensure_request(
                    appointment_id,
                    public_base_url=self.public_base_url,
                    rotate=rotate_confirmation or event_name == "appointment_rescheduled",
                )
                if request is not None:
                    context["confirmation_url"] = request["url"]
                    context["confirmation_deadline"] = request["confirmation_deadline"]
                    template_key = "appointment_confirmation_request"
                    body = await self._template_body(template_key, "whatsapp")
                    context["message"] = self._render(body, context)
                    await self._enqueue(
                        appointment_id=appointment_id,
                        template_key=template_key,
                        channel="whatsapp",
                        recipient=str(context["customer_phone"]),
                        payload=context,
                        scheduled_at=datetime.now(UTC),
                    )
                    return

        channel = "whatsapp"
        for template_key in self._templates_for_event(event_name):
            body = await self._template_body(template_key, channel)
            message = self._render(body, context)
            scheduled_at = self._scheduled_at_for(template_key, context["starts_at"])
            await self._enqueue(
                appointment_id=appointment_id,
                template_key=template_key,
                channel=channel,
                recipient=str(context["customer_phone"]),
                payload={**context, "message": message},
                scheduled_at=scheduled_at,
            )

    async def notify_tenant_confirmation_result(
        self,
        appointment_id: str,
        template_key: str,
    ) -> bool:
        recipient = str(
            await self._setting("tenant_notification_whatsapp", "") or ""
        ).strip()
        if not recipient:
            return False
        context = await self._appointment_context(appointment_id)
        if context is None:
            return False
        body = await self._template_body(template_key, "whatsapp")
        message = self._render(body, context)
        await self._enqueue(
            appointment_id=appointment_id,
            template_key=template_key,
            channel="whatsapp",
            recipient=recipient,
            payload={**context, "message": message, "audience": "tenant"},
            scheduled_at=datetime.now(UTC),
        )
        return True

    async def list_templates(
        self,
        *,
        channel: str | None = None,
        active: bool | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: dict[str, Any] = {}
        if channel:
            clauses.append("channel=:channel")
            params["channel"] = channel
        if active is not None:
            clauses.append("active=:active")
            params["active"] = active
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select id::text, key, channel, body, active, created_at
                    from notification_templates
                    where {' and '.join(clauses)}
                    order by key asc
                    """
                ),
                params,
            )
        ).mappings().all()
        return [self._row(row) for row in rows]

    async def upsert_template(
        self,
        *,
        key: str,
        channel: str,
        body: str,
        active: bool = True,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    insert into notification_templates(key, channel, body, active)
                    values(:key, :channel, :body, :active)
                    on conflict (key) do update set
                        channel=excluded.channel,
                        body=excluded.body,
                        active=excluded.active
                    returning id::text, key, channel, body, active, created_at
                    """
                ),
                {
                    "key": key,
                    "channel": channel,
                    "body": body,
                    "active": active,
                },
            )
        ).mappings().one()
        await self.session.commit()
        return self._row(row)

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where = "where status=:status" if status else ""
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        rows = (
            await self.session.execute(
                text(
                    f"""
                    select id::text, appointment_id::text, channel, recipient,
                           template_key, payload, scheduled_at, sent_at, status, error
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
            payload = self._normalize_payload(row["payload"])
            message = str(payload.get("message", ""))
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
            except Exception as exc:
                await self.session.execute(
                    text(
                        "update notification_jobs set status='FAILED', "
                        "error=:error where id=cast(:id as uuid)"
                    ),
                    {"id": row["id"], "error": str(exc)[:1000]},
                )
                failed += 1
        await self.session.commit()
        return {"sent": sent, "failed": failed, "total": len(rows)}
