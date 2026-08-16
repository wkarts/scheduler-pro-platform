from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
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


@router.post("/process-due")
async def process_due_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await NotificationService(session).process_due(limit=limit))
