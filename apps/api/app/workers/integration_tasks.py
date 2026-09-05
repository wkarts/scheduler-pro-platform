"""Bounded sweeps and isolated webhook workers; durable database claims own retries."""

import logging

from sqlalchemy import text

from app.integration_services.auth import integration_session
from app.integration_services.webhooks import cleanup, drain
from app.services.tenant_resolver import TenantResolver
from app.workers.celery_app import celery_app, typed_task
from app.workers.tasks import _run

logger = logging.getLogger("scheduler.integration-services")


async def _sweep() -> dict[str, int]:
    # Cursor and throttle survive process restarts; no whole-fleet list in memory.
    async with integration_session(None) as session:
        row = (
            await session.execute(
                text(
                    "update service_integration_sweep set next_run_at=now()+interval '50 seconds' "
                    "where id=1 and next_run_at<=now() returning last_tenant_id::text"
                )
            )
        ).first()
        if row is None:
            return {"queued": 0}
        tenants = list(
            (
                await session.execute(
                    text(
                        "select id::text from tenants where status='ACTIVE' "
                        "and (cast(:cursor as uuid) is null or id>cast(:cursor as uuid)) order by id limit 50"
                    ),
                    {"cursor": row[0]},
                )
            ).scalars()
        )
        await session.commit()
    # Publishing and outbound HTTP never retain a database session or engine lease.
    celery_app.send_task(
        "app.workers.integration_tasks.deliver",
        kwargs={"tenant_id": None},
        queue="webhooks",
        routing_key="webhooks",
        expires=180,
    )
    for tenant_id in tenants:
        celery_app.send_task(
            "app.workers.integration_tasks.deliver",
            kwargs={"tenant_id": tenant_id},
            queue="webhooks",
            routing_key="webhooks",
            expires=180,
        )
    async with integration_session(None) as session:
        await session.execute(
            text(
                "update service_integration_sweep set last_tenant_id=cast(:cursor as uuid) where id=1"
            ),
            {"cursor": tenants[-1] if len(tenants) == 50 else None},
        )
        await session.commit()
    return {"queued": len(tenants) + 1}


@typed_task(name="app.workers.integration_tasks.sweep")
def sweep() -> dict[str, int]:
    return dict(_run(_sweep()))


async def _deliver(tenant_id: str | None) -> dict[str, int]:
    context = None
    if tenant_id:
        async with integration_session(None) as session:
            context = await TenantResolver(session).resolve_by_id(tenant_id)
    result = await drain(context)
    # Purging completed history never releases processing/unknown idempotency keys.
    await cleanup(context)
    return result


@typed_task(name="app.workers.integration_tasks.deliver")
def deliver(tenant_id: str | None = None) -> dict[str, int]:
    try:
        return dict(_run(_deliver(tenant_id)))
    except Exception as exc:
        logger.error(
            "webhook_scope_failed",
            extra={
                "tenant_id": tenant_id,
                "error_type": type(exc).__name__,
            },
        )
        raise
