import asyncio
import os
from collections.abc import Awaitable
from threading import Lock
from typing import Any

from sqlalchemy import text

from app.db.session import close_database_engines, platform_session, tenant_session
from app.services.agenda_report_delivery_service import AgendaReportDeliveryService
from app.services.notification_dispatcher import TenantNotificationDispatcher
from app.services.tenant_resolver import TenantResolver
from app.workers.celery_app import typed_task

_loop: asyncio.AbstractEventLoop | None = None
_loop_pid: int | None = None
_loop_guard = Lock()


def _event_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_pid
    pid = os.getpid()
    if _loop_pid != pid:
        _loop = None
        _loop_pid = pid
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def _run(coro: Awaitable[Any]) -> Any:
    with _loop_guard:
        loop = _event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)


async def _process_all_agenda_reports() -> dict[str, int]:
    tenant_ids: list[str] = []
    async for platform in platform_session():
        tenant_ids = list(
            (
                await platform.execute(
                    text(
                        """
                        select distinct t.id::text
                        from tenants t
                        join tenant_capabilities tc on tc.tenant_id=t.id
                        where t.status='ACTIVE'
                          and tc.capability_key='appointments'
                          and tc.enabled=true
                        order by t.id::text
                        """
                    )
                )
            ).scalars()
        )
        break

    checked = 0
    generated = 0
    queued = 0
    sent = 0
    failed = 0
    for tenant_id in tenant_ids:
        try:
            async for platform in platform_session():
                context = await TenantResolver(platform).resolve_by_id(
                    tenant_id,
                    require_active=True,
                )
                break
            else:
                continue
            async for session in tenant_session(context):
                checked += 1
                result = await AgendaReportDeliveryService(
                    session,
                    context,
                ).process_due_schedules()
                generated += int(result.get("generated", 0))
                queued_now = int(result.get("queued", 0))
                queued += queued_now
                if queued_now:
                    delivery = await TenantNotificationDispatcher(session).process_due(limit=50)
                    sent += int(delivery.get("sent", 0))
                    failed += int(delivery.get("failed", 0))
                break
        except Exception:  # noqa: BLE001 - one tenant must not stop the sweep
            failed += 1

    return {
        "checked": checked,
        "generated": generated,
        "queued": queued,
        "sent": sent,
        "failed": failed,
    }


@typed_task(name="app.workers.agenda_report_tasks.process_all_agenda_reports")
def process_all_agenda_reports() -> dict[str, int]:
    try:
        return dict(_run(_process_all_agenda_reports()))
    finally:
        # Normal worker lifecycle keeps the loop alive; this branch only releases
        # cached engines if the task process is being torn down by the worker.
        if False:  # pragma: no cover - lifecycle is handled by Celery signals
            _run(close_database_engines())
