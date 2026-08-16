from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.responses import success
from app.services.appointment_service import AppointmentService

router = APIRouter()


class AppointmentCreate(BaseModel):
    customer_id: str
    service_id: str
    professional_id: str
    starts_at: datetime
    ends_at: datetime
    source: str = Field(default="web", max_length=32)


class AppointmentStatusUpdate(BaseModel):
    status: str = Field(min_length=3, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class AppointmentCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


@router.get("")
async def list_appointments(
    day: date | None = Query(default=None),
    professional_id: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    data = await AppointmentService(session).list_appointments(
        day=day,
        professional_id=professional_id,
        customer_id=customer_id,
        status=status,
    )
    return success(data)


@router.post("")
async def create_appointment(
    payload: AppointmentCreate,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    appointment = await AppointmentService(session).create(payload.model_dump())
    return success({"id": appointment.id, "status": appointment.status})


@router.get("/{appointment_id}")
async def get_appointment(
    appointment_id: str,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await AppointmentService(session).get(appointment_id))


@router.patch("/{appointment_id}/status")
async def update_status(
    appointment_id: str,
    payload: AppointmentStatusUpdate,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await AppointmentService(session).update_status(appointment_id, payload.status, payload.reason))


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: str,
    payload: AppointmentCancel,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await AppointmentService(session).cancel(appointment_id, payload.reason))
