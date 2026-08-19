from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.appointment_service import AppointmentService

router = APIRouter()


@router.get("")
async def availability(
    day: date = Query(...),
    professional_id: str = Query(...),
    service_id: str | None = Query(default=None),
    slot_minutes: int = Query(default=30, ge=5, le=240),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    slots = await AppointmentService(
        session,
        timezone=context.timezone,
    ).availability(
        day=day,
        professional_id=professional_id,
        service_id=service_id,
        slot_minutes=slot_minutes,
    )
    return success(slots)
