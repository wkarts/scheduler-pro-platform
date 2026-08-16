import asyncio
import re
from typing import Any

from sqlalchemy import text

from app.db.session import platform_session, tenant_session
from app.services.appointment_service import AppointmentService
from app.services.notification_dispatcher import TenantNotificationDispatcher
from app.services.provisioning_runtime import ProvisioningRuntime
from app.services.tenant_resolver import TenantResolver
from app.workers.celery_app import typed_task


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _run_provisioning(job_id: str) -> dict[str, object]:
    async for session in platform_session():
        await ProvisioningRuntime(session).run_job(job_id)
        return {"job_id": job_id, "processed": True}
    return {"job_id": job_id, "processed": False}


@typed_task(name="app.workers.tasks.run_provisioning")
def run_provisioning(
    job_id: str,
    tenant_id: str,
    correlation_id: str,
) -> dict[str, object]:
    result = dict(_run(_run_provisioning(job_id)))
    result.update({"tenant_id": tenant_id, "correlation_id": correlation_id})
    return result


def _text_from_webhook(payload: dict[str, Any]) -> str:
    raw_data = payload.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else payload
    raw_message = data.get("message")
    message: dict[str, Any] = raw_message if isinstance(raw_message, dict) else {}
    raw_extended = message.get("extendedTextMessage")
    extended: dict[str, Any] = raw_extended if isinstance(raw_extended, dict) else {}
    return str(
        message.get("conversation")
        or extended.get("text")
        or data.get("body")
        or payload.get("body")
        or ""
    ).strip()


def _phone_from_webhook(payload: dict[str, Any]) -> str:
    raw_data = payload.get("data")
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else payload
    raw_key = data.get("key")
    key: dict[str, Any] = raw_key if isinstance(raw_key, dict) else {}
    jid = str(
        key.get("remoteJid")
        or data.get("remoteJid")
        or payload.get("sender")
        or ""
    )
    return re.sub(r"\D", "", jid.split("@", 1)[0])


async def _process_whatsapp_event(
    tenant_id: str,
    event_id: str,
) -> dict[str, object]:
    async for platform in platform_session():
        context = await TenantResolver(platform).resolve_by_id(
            tenant_id,
            require_active=True,
        )
        break
    else:
        return {"tenant_id": tenant_id, "event_id": event_id, "processed": False}

    async for session in tenant_session(context):
        payload_value = await session.scalar(
            text("select payload from whatsapp_events where id=:id::uuid"),
            {"id": event_id},
        )
        payload: dict[str, Any] = (
            payload_value if isinstance(payload_value, dict) else {}
        )
        command = _text_from_webhook(payload).strip().upper()
        phone = _phone_from_webhook(payload)
        action = "ignored"
        appointment_id: str | None = None

        if command in {
            "CONFIRMAR",
            "CONFIRMO",
            "SIM CONFIRMAR",
            "SIM, CONFIRMAR",
        } and phone:
            appointment_id = await session.scalar(
                text(
                    """
                    select a.id::text
                    from appointments a
                    join customers c on c.id=a.customer_id
                    where regexp_replace(coalesce(c.phone,''), '\\D', '', 'g') = :phone
                      and a.status in ('PENDING','AWAITING_CONFIRMATION')
                      and a.starts_at >= now() - interval '2 hours'
                    order by a.starts_at asc
                    limit 1
                    """
                ),
                {"phone": phone},
            )
            if appointment_id:
                await AppointmentService(session).update_status(
                    appointment_id,
                    "CONFIRMED",
                    "Confirmado via WhatsApp",
                )
                action = "confirmed"
        elif command in {"CANCELAR", "CANCELAR AGENDAMENTO"} and phone:
            appointment_id = await session.scalar(
                text(
                    """
                    select a.id::text
                    from appointments a
                    join customers c on c.id=a.customer_id
                    where regexp_replace(coalesce(c.phone,''), '\\D', '', 'g') = :phone
                      and a.status in ('PENDING','AWAITING_CONFIRMATION','CONFIRMED')
                      and a.starts_at >= now() - interval '2 hours'
                    order by a.starts_at asc
                    limit 1
                    """
                ),
                {"phone": phone},
            )
            if appointment_id:
                await AppointmentService(session).cancel(
                    appointment_id,
                    "Cancelado via WhatsApp",
                )
                action = "cancelled"

        await session.execute(
            text(
                """
                update outbox_events
                set status='processed'
                where aggregate_id=:event_id
                  and event_name='whatsapp.webhook.received'
                """
            ),
            {"event_id": event_id},
        )
        await session.commit()
        return {
            "tenant_id": tenant_id,
            "event_id": event_id,
            "processed": True,
            "action": action,
            "appointment_id": appointment_id,
        }
    return {"tenant_id": tenant_id, "event_id": event_id, "processed": False}


@typed_task(name="app.workers.tasks.process_whatsapp_webhook")
def process_whatsapp_webhook(
    tenant_id: str,
    event_id: str,
    correlation_id: str,
) -> dict[str, object]:
    result = dict(_run(_process_whatsapp_event(tenant_id, event_id)))
    result["correlation_id"] = correlation_id
    return result


async def _process_due_notifications(tenant_id: str) -> dict[str, object]:
    async for platform in platform_session():
        context = await TenantResolver(platform).resolve_by_id(
            tenant_id,
            require_active=True,
        )
        break
    else:
        return {"tenant_id": tenant_id, "processed": False}

    async for session in tenant_session(context):
        result = await TenantNotificationDispatcher(session).process_due(limit=100)
        return {"tenant_id": tenant_id, "processed": True, **result}
    return {"tenant_id": tenant_id, "processed": False}


@typed_task(name="app.workers.tasks.process_due_notifications")
def process_due_notifications(
    tenant_id: str,
    correlation_id: str,
) -> dict[str, object]:
    result = dict(_run(_process_due_notifications(tenant_id)))
    result["correlation_id"] = correlation_id
    return result


async def _process_all_due_notifications() -> dict[str, object]:
    tenant_ids: list[str] = []
    async for platform in platform_session():
        tenant_ids = list(
            (
                await platform.execute(
                    text("select id::text from tenants where status='ACTIVE'")
                )
            ).scalars()
        )
        break

    tenant_count = 0
    sent_count = 0
    failed_count = 0
    for tenant_id in tenant_ids:
        try:
            result = await _process_due_notifications(tenant_id)
        except Exception:  # noqa: BLE001 - one tenant must not stop the sweep
            failed_count += 1
            continue

        tenant_count += 1
        sent_value = result.get("sent", 0)
        failed_value = result.get("failed", 0)
        if isinstance(sent_value, int):
            sent_count += sent_value
        if isinstance(failed_value, int):
            failed_count += failed_value

    totals: dict[str, object] = {
        "tenants": tenant_count,
        "sent": sent_count,
        "failed": failed_count,
    }
    return totals


@typed_task(name="app.workers.tasks.process_all_due_notifications")
def process_all_due_notifications() -> dict[str, object]:
    return dict(_run(_process_all_due_notifications()))


@typed_task(name="app.workers.tasks.run_build_job")
def run_build_job(
    job_id: str,
    tenant_id: str,
    target: str,
    correlation_id: str,
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "target": target,
        "correlation_id": correlation_id,
        "queued": True,
        "note": "Build dispatch is handled by the Build Manager integration.",
    }
