from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.errors import APIError
from app.core.responses import success
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("")
async def notification_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await NotificationService(session).list_jobs(status=status, limit=limit))


@router.get("/templates")
async def notification_templates(
    channel: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await NotificationService(session).list_templates(channel=channel, active=active))


@router.put("/templates/{template_key}")
async def upsert_notification_template(
    template_key: str,
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    channel = str(payload.get("channel") or "whatsapp")
    body = str(payload.get("body") or "").strip()
    active = bool(payload.get("active", True))
    if not body:
        raise APIError("NOTIFICATION_TEMPLATE_BODY_REQUIRED", "Corpo do template é obrigatório.", 422)
    return success(await NotificationService(session).upsert_template(key=template_key, channel=channel, body=body, active=active))


@router.post("/process-due")
async def process_due_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await NotificationService(session).process_due(limit=limit))
