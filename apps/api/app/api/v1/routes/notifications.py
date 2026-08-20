from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.errors import APIError
from app.core.responses import success
from app.services.notification_dispatcher import TenantNotificationDispatcher
from app.services.notification_service import NotificationService
from app.services.tenant_mail_service import TenantMailService

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
    channel = str(payload.get("channel") or "whatsapp").strip().lower()
    if channel not in {"whatsapp", "email"}:
        raise APIError("NOTIFICATION_TEMPLATE_CHANNEL_INVALID", "Canal de mensagem inválido.", 422)
    body = str(payload.get("body") or "").strip()
    active = bool(payload.get("active", True))
    subject_value = payload.get("subject")
    subject = str(subject_value).strip() if subject_value is not None else None
    if not body:
        raise APIError("NOTIFICATION_TEMPLATE_BODY_REQUIRED", "Corpo do template é obrigatório.", 422)
    if subject is not None and len(subject) > 240:
        raise APIError("NOTIFICATION_TEMPLATE_SUBJECT_TOO_LONG", "O assunto do e-mail deve ter no máximo 240 caracteres.", 422)
    if channel != "email":
        subject = None
    return success(
        await NotificationService(session).upsert_template(
            key=template_key,
            channel=channel,
            body=body,
            active=active,
            subject=subject,
        )
    )


@router.get("/smtp")
async def smtp_settings(
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await TenantMailService(session).status())


@router.put("/smtp")
async def configure_smtp(
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await TenantMailService(session).configure(payload))


@router.post("/smtp/test")
async def test_smtp(
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await TenantMailService(session).send_test(str(payload.get("recipient") or "")))


@router.post("/process-due")
async def process_due_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await TenantNotificationDispatcher(session).process_due(limit=limit))
