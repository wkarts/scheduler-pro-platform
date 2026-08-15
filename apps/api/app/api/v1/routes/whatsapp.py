from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.responses import success
from app.services.whatsapp_provider import WhatsAppProviderFactory

router = APIRouter()


@router.post("/connect")
async def connect() -> dict[str, Any]:
    provider = WhatsAppProviderFactory.make()
    return success(await provider.connect_instance())


@router.get("/status")
async def status() -> dict[str, Any]:
    provider = WhatsAppProviderFactory.make()
    return success(await provider.connection_status())


@router.post("/webhook/{integration_key}")
async def webhook(
    integration_key: str,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    payload: dict[str, Any] = await request.json()
    provider_event_id = str(
        payload.get("id")
        or payload.get("event_id")
        or request.headers.get("x-provider-event-id")
        or ""
    )
    if not provider_event_id:
        provider_event_id = f"missing-{integration_key}-{hash(str(payload))}"
    # Persistência idempotente real entra via WhatsAppEvent UNIQUE provider_event_id.
    return success(
        {
            "accepted": True,
            "integration_key": integration_key,
            "provider_event_id": provider_event_id,
        }
    )
