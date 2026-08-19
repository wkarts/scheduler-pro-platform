import asyncio
import os
import re
from collections.abc import Awaitable
from threading import Lock
from typing import Any

from celery.signals import worker_process_shutdown
from sqlalchemy import text

from app.core.config import settings
from app.db.session import close_database_engines, platform_session, tenant_session
from app.services.appointment_confirmation_service import AppointmentConfirmationService
from app.services.appointment_service import AppointmentService
from app.services.domain_provisioning_service import DomainProvisioningService
from app.services.notification_dispatcher import TenantNotificationDispatcher
from app.services.provisioning_runtime import ProvisioningRuntime
from app.services.realtime_service import RealtimeEventService, WebPushService
from app.services.tenant_resolver import TenantResolver
from app.workers.celery_app import typed_task

_worker_loop: asyncio.AbstractEventLoop | None = None
_worker_loop_pid: int | None = None
_worker_loop_guard = Lock()


def _worker_event_loop() -> asyncio.AbstractEventLoop:
    """Return one persistent asyncio loop for the current Celery worker process."""

    global _worker_loop, _worker_loop_pid

    pid = os.getpid()
    if _worker_loop_pid != pid:
        _worker_loop = None
        _worker_loop_pid = pid

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    return _worker_loop


def _run(coro: Awaitable[Any]) -> Any:
    with _worker_loop_guard:
        loop = _worker_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


def _shutdown_worker_async_runtime(*_args: Any, **_kwargs: Any) -> None:
    global _worker_loop, _worker_loop_pid

    with _worker_loop_guard:
        loop = _worker_loop
        if loop is None or loop.is_closed():
            _worker_loop = None
            _worker_loop_pid = None
            return

        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(close_database_engines())
        finally:
            loop.close()
            asyncio.set_event_loop(None)
            _worker_loop = None
            _worker_loop_pid = None


worker_process_shutdown.connect(_shutdown_worker_async_runtime, weak=False)


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


async def _reconcile_managed_domains() -> dict[str, object]:
    if settings.tls_provisioning_mode != "local_acme":
        return {"enabled": False, "checked": 0, "active": 0, "failed": 0}

    root = settings.tenant_domain_root.strip().lower().rstrip(".")
    suffix = f"%.{root}"
    checked = 0
    active = 0
    failed = 0

    async for session in platform_session():
        domain_ids = list(
            (
                await session.execute(
                    text(
                        """
                        select id::text
                        from domains
                        where is_temporary=true
                           or lower(hostname)=:root
                           or lower(hostname) like :suffix
                        order by id asc
                        """
                    ),
                    {"root": root, "suffix": suffix},
                )
            ).scalars()
        )
        service = DomainProvisioningService(session)
        for domain_id in domain_ids:
            checked += 1
            try:
                result = await service.check_domain(str(domain_id))
                if str(result.get("status") or "").upper() == "ACTIVE":
                    active += 1
                else:
                    failed += 1
            except Exception:  # noqa: BLE001
                await session.rollback()
                failed += 1
        return {
            "enabled": True,
            "checked": checked,
            "active": active,
            "failed": failed,
            "dns_proxied": settings.cloudflare_temporary_record_proxied,
        }

    return {"enabled": True, "checked": 0, "active": 0, "failed": 0}


@typed_task(name="app.workers.tasks.reconcile_managed_domains")
def reconcile_managed_domains() -> dict[str, object]:
    return dict(_run(_reconcile_managed_domains()))


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


async def _capability_enabled(tenant_id: str, key: str) -> bool:
    async for platform in platform_session():
        enabled = await platform.scalar(
            text(
                """
                select enabled from tenant_capabilities
                where tenant_id=cast(:tenant_id as uuid) and capability_key=:key
                limit 1
                """
            ),
            {"tenant_id": tenant_id, "key": key},
        )
        return enabled is True
    return False


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
            text("select payload from whatsapp_events where id=cast(:id as uuid)"),
            {"id": event_id},
        )
        payload: dict[str, Any] = (
            payload_value if isinstance(payload_value, dict) else {}
        )
        command = _text_from_webhook(payload).strip().upper()
        phone = _phone_from_webhook(payload)
        action = "ignored"
        appointment_id: str | None = None
        realtime_type: str | None = None

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
                realtime_type = "appointment.customer_confirmed"
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
                realtime_type = "appointment.customer_cancelled"

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

        if appointment_id and realtime_type:
            realtime = await RealtimeEventService(session).emit_appointment(
                appointment_id,
                realtime_type,
                actor="customer-whatsapp",
            )
            if realtime and await _capability_enabled(tenant_id, "notifications"):
                await WebPushService(session).dispatch_event(realtime)

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


async def _dispatch_realtime_push(tenant_id: str, event_id: str) -> dict[str, object]:
    if not await _capability_enabled(tenant_id, "notifications"):
        return {
            "tenant_id": tenant_id,
            "event_id": event_id,
            "processed": False,
            "reason": "notifications capability disabled",
        }

    async for platform in platform_session():
        context = await TenantResolver(platform).resolve_by_id(
            tenant_id,
            require_active=True,
        )
        break
    else:
        return {"tenant_id": tenant_id, "event_id": event_id, "processed": False}

    async for session in tenant_session(context):
        event = await RealtimeEventService(session).get_event(event_id)
        if event is None:
            return {"tenant_id": tenant_id, "event_id": event_id, "processed": False}
        result = await WebPushService(session).dispatch_event(event)
        return {
            "tenant_id": tenant_id,
            "event_id": event_id,
            "processed": True,
            **result,
        }
    return {"tenant_id": tenant_id, "event_id": event_id, "processed": False}


@typed_task(name="app.workers.tasks.dispatch_realtime_push")
def dispatch_realtime_push(tenant_id: str, event_id: str) -> dict[str, object]:
    return dict(_run(_dispatch_realtime_push(tenant_id, event_id)))


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
                    text(
                        """
                        select t.id::text
                        from tenants t
                        join tenant_capabilities tc on tc.tenant_id=t.id
                        where t.status='ACTIVE'
                          and tc.capability_key='notifications'
                          and tc.enabled=true
                        """
                    )
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
        except Exception:  # noqa: BLE001
            failed_count += 1
            continue

        tenant_count += 1
        sent_value = result.get("sent", 0)
        failed_value = result.get("failed", 0)
        if isinstance(sent_value, int):
            sent_count += sent_value
        if isinstance(failed_value, int):
            failed_count += failed_value

    return {
        "tenants": tenant_count,
        "sent": sent_count,
        "failed": failed_count,
    }


@typed_task(name="app.workers.tasks.process_all_due_notifications")
def process_all_due_notifications() -> dict[str, object]:
    return dict(_run(_process_all_due_notifications()))


async def _expire_confirmation_requests(tenant_id: str) -> dict[str, object]:
    async for platform in platform_session():
        context = await TenantResolver(platform).resolve_by_id(
            tenant_id,
            require_active=True,
        )
        break
    else:
        return {"tenant_id": tenant_id, "processed": False}

    async for session in tenant_session(context):
        result = await AppointmentConfirmationService(session).expire_due(limit=300)
        appointment_ids_value = result.get("appointment_ids", [])
        appointment_ids = (
            [str(value) for value in appointment_ids_value]
            if isinstance(appointment_ids_value, list)
            else []
        )
        push_enabled = await _capability_enabled(tenant_id, "notifications")
        for appointment_id in appointment_ids:
            realtime = await RealtimeEventService(session).emit_appointment(
                appointment_id,
                "appointment.confirmation_expired",
                actor="scheduler",
            )
            if realtime and push_enabled:
                await WebPushService(session).dispatch_event(realtime)
        if appointment_ids and push_enabled:
            await TenantNotificationDispatcher(session).process_due(limit=100)
        return {
            "tenant_id": tenant_id,
            "processed": True,
            "expired": result.get("expired", 0),
            "failed": result.get("failed", 0),
        }
    return {"tenant_id": tenant_id, "processed": False}


async def _expire_all_confirmation_requests() -> dict[str, object]:
    tenant_ids: list[str] = []
    async for platform in platform_session():
        tenant_ids = list(
            (
                await platform.execute(
                    text(
                        """
                        select t.id::text
                        from tenants t
                        join tenant_capabilities tc on tc.tenant_id=t.id
                        where t.status='ACTIVE'
                          and tc.capability_key='appointments'
                          and tc.enabled=true
                        """
                    )
                )
            ).scalars()
        )
        break

    expired = 0
    failed = 0
    processed = 0
    for tenant_id in tenant_ids:
        try:
            result = await _expire_confirmation_requests(tenant_id)
            processed += 1
            expired_value = result.get("expired", 0)
            failed_value = result.get("failed", 0)
            if isinstance(expired_value, int):
                expired += expired_value
            if isinstance(failed_value, int):
                failed += failed_value
        except Exception:  # noqa: BLE001
            failed += 1
    return {
        "tenants": processed,
        "expired": expired,
        "failed": failed,
    }


@typed_task(name="app.workers.tasks.expire_all_confirmation_requests")
def expire_all_confirmation_requests() -> dict[str, object]:
    return dict(_run(_expire_all_confirmation_requests()))


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
