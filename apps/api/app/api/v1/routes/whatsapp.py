import json
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.config import settings
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.whatsapp_provider import WhatsAppProvider, WhatsAppProviderFactory
from app.workers.celery_app import celery_app

router = APIRouter()


class SendTextRequest(BaseModel):
    to: str = Field(min_length=8, max_length=40)
    message: str = Field(min_length=1, max_length=4096)


async def _tenant_provider(session: AsyncSession, context: TenantContext) -> tuple[str, WhatsAppProvider]:
    instance_name = await session.scalar(text("select instance_name from whatsapp_integrations where name='default' limit 1"))
    if not instance_name:
        instance_name = f"{settings.evolution_instance_name}-{context.slug}"[:160]
        await session.execute(
            text(
                """
                insert into whatsapp_integrations(name, provider, instance_name, status, settings)
                values('default', 'evolution', :instance_name, 'DISCONNECTED', '{}'::jsonb)
                on conflict(name) do update set instance_name=excluded.instance_name
                """
            ),
            {"instance_name": instance_name},
        )
        await session.commit()
    return str(instance_name), WhatsAppProviderFactory.make(str(instance_name))


@router.post("/connect")
async def connect(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    instance_name, provider = await _tenant_provider(session, context)
    result = await provider.connect_instance()
    await session.execute(
        text("update whatsapp_integrations set status='CONNECTING', settings=cast(:settings as jsonb), updated_at=now() where name='default'"),
        {"settings": json.dumps({"last_connect": result}, ensure_ascii=False, default=str)},
    )
    await session.commit()
    return success({"instance_name": instance_name, **result})


@router.get("/status")
async def status(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    instance_name, provider = await _tenant_provider(session, context)
    result = await provider.connection_status()
    instance_data = result.get("instance") if isinstance(result.get("instance"), dict) else {}
    state = str(instance_data.get("state") or "unknown").lower()
    db_status = "CONNECTED" if state in {"open", "connected"} else "DISCONNECTED" if state in {"close", "closed", "disconnected"} else "CONNECTING"
    await session.execute(
        text("update whatsapp_integrations set status=:status, settings=cast(:settings as jsonb), updated_at=now() where name='default'"),
        {"status": db_status, "settings": json.dumps({"last_status": result}, ensure_ascii=False, default=str)},
    )
    await session.commit()
    return success({"instance_name": instance_name, "status": db_status, "provider": result})


@router.post("/send-text")
async def send_text(
    payload: SendTextRequest,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    instance_name, provider = await _tenant_provider(session, context)
    result = await provider.send_text(payload.to, payload.message)
    return success({"instance_name": instance_name, "message": result})


@router.post("/webhook/{integration_key}")
async def webhook(
    integration_key: str,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    payload = cast(dict[str, Any], await request.json())
    key_value = payload.get("key")
    key: dict[str, Any] = key_value if isinstance(key_value, dict) else {}
    provider_event_id = str(
        payload.get("id")
        or payload.get("event_id")
        or key.get("id")
        or request.headers.get("x-provider-event-id")
        or ""
    )
    if not provider_event_id:
        provider_event_id = f"missing-{integration_key}-{abs(hash(str(payload)))}"
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    inserted = await session.scalar(
        text(
            """
            insert into whatsapp_events(provider_event_id, integration_key, payload)
            values(:provider_event_id, :integration_key, cast(:payload as jsonb))
            on conflict(provider_event_id) do nothing
            returning id::text
            """
        ),
        {"provider_event_id": provider_event_id, "integration_key": integration_key, "payload": payload_json},
    )
    if inserted:
        await session.execute(
            text(
                """
                insert into outbox_events(event_name, aggregate_id, payload)
                values('whatsapp.webhook.received', :aggregate_id, cast(:payload as jsonb))
                """
            ),
            {"aggregate_id": inserted, "payload": json.dumps({"integration_key": integration_key, "provider_event_id": provider_event_id})},
        )
    await session.commit()
    if inserted:
        celery_app.send_task(
            "app.workers.tasks.process_whatsapp_webhook",
            args=[context.tenant_id, str(inserted), f"whatsapp-{inserted}"],
            queue="whatsapp",
        )
    return success({"accepted": True, "duplicate": inserted is None, "queued": inserted is not None, "integration_key": integration_key, "provider_event_id": provider_event_id})
