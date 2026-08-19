from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.secrets import seal_secret, secret_resolver


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


_EVENT_MESSAGES: dict[str, tuple[str, str]] = {
    "appointment.created": (
        "Novo agendamento",
        "{customer_name} foi agendado para {starts_at_label}.",
    ),
    "appointment.confirmed": (
        "Agendamento confirmado",
        "{customer_name} está confirmado para {starts_at_label}.",
    ),
    "appointment.customer_confirmed": (
        "Cliente confirmou",
        "{customer_name} confirmou o atendimento de {service_name} para {starts_at_label}.",
    ),
    "appointment.cancelled": (
        "Agendamento cancelado",
        "O atendimento de {customer_name} em {starts_at_label} foi cancelado.",
    ),
    "appointment.customer_cancelled": (
        "Cliente cancelou",
        "{customer_name} cancelou o atendimento de {service_name}. O horário foi liberado.",
    ),
    "appointment.rescheduled": (
        "Agendamento remarcado",
        "{customer_name} foi remarcado para {starts_at_label} e aguarda nova confirmação.",
    ),
    "appointment.confirmation_expired": (
        "Prazo de confirmação expirou",
        "{customer_name} não confirmou a tempo. O horário de {starts_at_label} foi liberado.",
    ),
    "appointment.checked_in": (
        "Check-in realizado",
        "{customer_name} chegou para o atendimento.",
    ),
    "appointment.in_progress": (
        "Atendimento iniciado",
        "O atendimento de {customer_name} foi iniciado.",
    ),
    "appointment.completed": (
        "Atendimento concluído",
        "O atendimento de {customer_name} foi concluído.",
    ),
    "appointment.no_show": (
        "Não compareceu",
        "{customer_name} foi marcado como não compareceu.",
    ),
}


class RealtimeEventService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def emit_appointment(
        self,
        appointment_id: str,
        event_type: str,
        *,
        actor: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    select a.id::text, a.starts_at, a.ends_at, a.status,
                           c.name as customer_name, c.phone as customer_phone,
                           s.name as service_name,
                           p.name as professional_name
                    from appointments a
                    join customers c on c.id=a.customer_id
                    join services s on s.id=a.service_id
                    join professionals p on p.id=a.professional_id
                    where a.id=cast(:appointment_id as uuid)
                    """
                ),
                {"appointment_id": appointment_id},
            )
        ).mappings().first()
        if row is None:
            return {}

        starts_at = row["starts_at"]
        starts_at_label = (
            starts_at.strftime("%d/%m/%Y %H:%M")
            if isinstance(starts_at, datetime)
            else "horário informado"
        )
        payload: dict[str, Any] = {
            "appointment_id": row["id"],
            "starts_at": row["starts_at"],
            "ends_at": row["ends_at"],
            "status": row["status"],
            "customer_name": row["customer_name"],
            "customer_phone": row["customer_phone"],
            "service_name": row["service_name"],
            "professional_name": row["professional_name"],
            "actor": actor,
            "url": "/#agenda",
            **(extra or {}),
        }
        title, message_template = _EVENT_MESSAGES.get(
            event_type,
            ("Agenda atualizada", "O agendamento de {customer_name} foi atualizado."),
        )
        message = message_template.format(
            customer_name=row["customer_name"],
            service_name=row["service_name"],
            professional_name=row["professional_name"],
            starts_at_label=starts_at_label,
        )
        inserted = (
            await self.session.execute(
                text(
                    """
                    insert into tenant_realtime_events(
                      event_type, appointment_id, title, message, payload
                    ) values(
                      :event_type, cast(:appointment_id as uuid), :title, :message,
                      cast(:payload as jsonb)
                    )
                    returning sequence, id::text, event_type, appointment_id::text,
                              title, message, payload, created_at
                    """
                ),
                {
                    "event_type": event_type,
                    "appointment_id": appointment_id,
                    "title": title,
                    "message": message,
                    "payload": json.dumps(payload, ensure_ascii=False, default=str),
                },
            )
        ).mappings().one()
        await self.session.commit()
        return dict(inserted)

    async def list_after(self, sequence: int, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    select sequence, id::text, event_type, appointment_id::text,
                           title, message, payload, created_at
                    from tenant_realtime_events
                    where sequence > :sequence
                    order by sequence asc
                    limit :limit
                    """
                ),
                {"sequence": max(sequence, 0), "limit": min(max(limit, 1), 500)},
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    async def get_event(self, event_id: str) -> dict[str, Any] | None:
        row = (
            await self.session.execute(
                text(
                    """
                    select sequence, id::text, event_type, appointment_id::text,
                           title, message, payload, created_at
                    from tenant_realtime_events
                    where id=cast(:event_id as uuid)
                    limit 1
                    """
                ),
                {"event_id": event_id},
            )
        ).mappings().first()
        return dict(row) if row else None


class WebPushService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _setting(self, key: str) -> Any:
        return await self.session.scalar(
            text("select value from tenant_settings where key=:key limit 1"),
            {"key": key},
        )

    async def _write_setting(self, key: str, value: Any) -> None:
        await self.session.execute(
            text(
                """
                insert into tenant_settings(key, value, updated_at)
                values(:key, cast(:value as jsonb), now())
                on conflict(key) do update set value=excluded.value, updated_at=now()
                """
            ),
            {"key": key, "value": json.dumps(value)},
        )

    async def ensure_vapid_keys(self) -> tuple[str, str]:
        public_key = str(await self._setting("web_push_vapid_public_key") or "").strip()
        private_ref = str(await self._setting("web_push_vapid_private_key_ref") or "").strip()
        if public_key and private_ref:
            return public_key, secret_resolver.resolve(private_ref)

        private_key = ec.generate_private_key(ec.SECP256R1())
        private_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_raw = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        private_value = _b64url(private_der)
        public_key = _b64url(public_raw)
        await self._write_setting("web_push_vapid_public_key", public_key)
        await self._write_setting(
            "web_push_vapid_private_key_ref",
            seal_secret(private_value),
        )
        await self.session.commit()
        return public_key, private_value

    async def public_key(self) -> str:
        public_key, _ = await self.ensure_vapid_keys()
        return public_key

    async def subscribe(
        self,
        *,
        user_id: str,
        endpoint: str,
        p256dh: str,
        auth: str,
        expiration_time: int | None,
        user_agent: str | None,
        device_label: str | None,
    ) -> dict[str, Any]:
        row = (
            await self.session.execute(
                text(
                    """
                    insert into web_push_subscriptions(
                      user_id, endpoint, p256dh, auth, expiration_time,
                      user_agent, device_label, active, last_error, updated_at
                    ) values(
                      cast(:user_id as uuid), :endpoint, :p256dh, :auth,
                      :expiration_time, :user_agent, :device_label, true, null, now()
                    )
                    on conflict(endpoint) do update set
                      user_id=excluded.user_id,
                      p256dh=excluded.p256dh,
                      auth=excluded.auth,
                      expiration_time=excluded.expiration_time,
                      user_agent=excluded.user_agent,
                      device_label=excluded.device_label,
                      active=true,
                      last_error=null,
                      updated_at=now()
                    returning id::text, endpoint, active, device_label, created_at, updated_at
                    """
                ),
                {
                    "user_id": user_id,
                    "endpoint": endpoint,
                    "p256dh": p256dh,
                    "auth": auth,
                    "expiration_time": expiration_time,
                    "user_agent": (user_agent or "")[:500] or None,
                    "device_label": (device_label or "")[:160] or None,
                },
            )
        ).mappings().one()
        await self.session.commit()
        return dict(row)

    async def unsubscribe(self, *, user_id: str, endpoint: str) -> bool:
        deleted = await self.session.scalar(
            text(
                """
                delete from web_push_subscriptions
                where user_id=cast(:user_id as uuid) and endpoint=:endpoint
                returning id::text
                """
            ),
            {"user_id": user_id, "endpoint": endpoint},
        )
        await self.session.commit()
        return deleted is not None

    async def dispatch_event(self, event: dict[str, Any]) -> dict[str, int]:
        _, private_key = await self.ensure_vapid_keys()
        subscriptions = (
            await self.session.execute(
                text(
                    """
                    select id::text, endpoint, p256dh, auth
                    from web_push_subscriptions
                    where active=true
                    order by updated_at desc
                    limit 1000
                    """
                )
            )
        ).mappings().all()
        payload = {
            "title": event.get("title") or "Scheduler Pro",
            "body": event.get("message") or "Sua agenda foi atualizada.",
            "tag": f"scheduler-{event.get('appointment_id') or event.get('id')}",
            "url": (event.get("payload") or {}).get("url", "/#agenda")
            if isinstance(event.get("payload"), dict)
            else "/#agenda",
            "event_type": event.get("event_type"),
            "appointment_id": event.get("appointment_id"),
            "sequence": event.get("sequence"),
        }
        subject = settings.smtp_from_email or f"admin@{settings.public_platform_domain}"
        sent = 0
        failed = 0
        disabled = 0
        for subscription in subscriptions:
            info = {
                "endpoint": str(subscription["endpoint"]),
                "keys": {
                    "p256dh": str(subscription["p256dh"]),
                    "auth": str(subscription["auth"]),
                },
            }
            try:
                await asyncio.to_thread(
                    webpush,
                    subscription_info=info,
                    data=json.dumps(payload, ensure_ascii=False),
                    vapid_private_key=private_key,
                    vapid_claims={"sub": f"mailto:{subject}"},
                    ttl=3600,
                )
                await self.session.execute(
                    text(
                        """
                        update web_push_subscriptions
                        set last_success_at=now(), last_error=null, updated_at=now()
                        where id=cast(:id as uuid)
                        """
                    ),
                    {"id": subscription["id"]},
                )
                sent += 1
            except WebPushException as exc:
                status_code = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
                is_gone = status_code in {404, 410}
                await self.session.execute(
                    text(
                        """
                        update web_push_subscriptions
                        set active=:active, last_error=:error, updated_at=now()
                        where id=cast(:id as uuid)
                        """
                    ),
                    {
                        "id": subscription["id"],
                        "active": not is_gone,
                        "error": str(exc)[:1000],
                    },
                )
                disabled += int(is_gone)
                failed += 1
            except Exception as exc:  # noqa: BLE001 - provider failure is persisted
                await self.session.execute(
                    text(
                        """
                        update web_push_subscriptions
                        set last_error=:error, updated_at=now()
                        where id=cast(:id as uuid)
                        """
                    ),
                    {"id": subscription["id"], "error": str(exc)[:1000]},
                )
                failed += 1
        await self.session.commit()
        return {"sent": sent, "failed": failed, "disabled": disabled}
