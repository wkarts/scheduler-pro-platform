from contextlib import aclosing
from sqlalchemy import text

from app.db.session import platform_session, tenant_session
from app.services.agenda_report_delivery_service import AgendaReportDeliveryService
from app.services.notification_dispatcher import TenantNotificationDispatcher
from app.services.tenant_resolver import TenantResolver
from app.workers.celery_app import typed_task
from app.workers.tasks import _run


async def _process_all_agenda_reports() -> dict[str, int]:
    tenant_ids: list[str] = []
    async with aclosing(platform_session()) as _session_scope_13:
        async for platform in _session_scope_13:
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
            async with aclosing(platform_session()) as _session_scope_40:
                async for platform in _session_scope_40:
                    context = await TenantResolver(platform).resolve_by_id(
                        tenant_id,
                        require_active=True,
                    )
                    break
                else:
                    continue
            async with aclosing(tenant_session(context)) as _session_scope_48:
                async for session in _session_scope_48:
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
    # Same process, same loop and same shutdown/fork lifecycle as every other task.
    return dict(_run(_process_all_agenda_reports()))
