import json
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.responses import success
from app.services.whatsapp_provider import WhatsAppProviderFactory

router = APIRouter()


class SendTextRequest(BaseModel):
    to: str = Field(min_length=8, max_length=40)
    message: str = Field(min_length=1, max_length=4096)


@router.post("/connect")
async def connect() -> dict[str, Any]:
    provider = WhatsAppProviderFactory.make()
    return success(await provider.connect_instance())


@router.get("/status")
async def status() -> dict[str, Any]:
    provider = WhatsAppProviderFactory.make()
    return success(await provider.connection_status())


@router.post("/send-text")
async def send_text(payload: SendTextRequest) -> dict[str, Any]:
    return success(await WhatsAppProviderFactory.make().send_text(payload.to, payload.message))


@router.post("/webhook/{integration_key}")
async def webhook(
    integration_key: str,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
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
    return success({"accepted": True, "duplicate": inserted is None, "integration_key": integration_key, "provider_event_id": provider_event_id})
