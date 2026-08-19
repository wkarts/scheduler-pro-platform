import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_tenant_session,
    require_permission,
    require_tenant_capability,
)
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.realtime_service import RealtimeEventService, WebPushService

router = APIRouter()


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=16, max_length=2048)
    auth: str = Field(min_length=4, max_length=1024)


class PushSubscriptionPayload(BaseModel):
    endpoint: str = Field(min_length=20, max_length=4096)
    keys: PushKeys
    expiration_time: int | None = Field(default=None, alias="expirationTime")
    device_label: str | None = Field(default=None, max_length=160)


class PushUnsubscribePayload(BaseModel):
    endpoint: str = Field(min_length=20, max_length=4096)


@router.get(
    "/events",
    dependencies=[
        Depends(require_tenant_capability("appointments")),
        Depends(require_permission("appointments.read")),
    ],
)
async def event_stream(
    request: Request,
    after: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_tenant_session),
) -> StreamingResponse:
    service = RealtimeEventService(session)

    async def generate() -> AsyncIterator[str]:
        cursor = after
        while True:
            if await request.is_disconnected():
                break
            rows = await service.list_after(cursor, limit=100)
            # SELECT abre transação no AsyncSession. Fechar a transação após cada
            # leitura evita prender uma conexão PostgreSQL durante toda a vida do
            # SSE; a próxima iteração adquire conexão somente quando necessário.
            await session.rollback()
            if rows:
                for row in rows:
                    cursor = int(row["sequence"])
                    payload = json.dumps(row, ensure_ascii=False, default=str)
                    yield (
                        f"id: {cursor}\n"
                        f"event: {row['event_type']}\n"
                        f"data: {payload}\n\n"
                    )
            else:
                yield ": keepalive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/push/public-key",
    dependencies=[Depends(require_tenant_capability("notifications"))],
)
async def push_public_key(
    _: AuthPrincipal = Depends(require_permission("appointments.read")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success({"public_key": await WebPushService(session).public_key()})


@router.post(
    "/push/subscriptions",
    dependencies=[Depends(require_tenant_capability("notifications"))],
)
async def subscribe_push(
    payload: PushSubscriptionPayload,
    request: Request,
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await WebPushService(session).subscribe(
        user_id=principal.user_id,
        endpoint=payload.endpoint,
        p256dh=payload.keys.p256dh,
        auth=payload.keys.auth,
        expiration_time=payload.expiration_time,
        user_agent=request.headers.get("user-agent"),
        device_label=payload.device_label,
    )
    return success(data)


@router.delete(
    "/push/subscriptions",
    dependencies=[Depends(require_tenant_capability("notifications"))],
)
async def unsubscribe_push(
    payload: PushUnsubscribePayload,
    principal: AuthPrincipal = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    deleted = await WebPushService(session).unsubscribe(
        user_id=principal.user_id,
        endpoint=payload.endpoint,
    )
    return success({"deleted": deleted})
