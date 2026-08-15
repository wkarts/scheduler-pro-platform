from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
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


@router.post("")
async def create_appointment(payload: AppointmentCreate, session: AsyncSession = Depends(get_tenant_session)):
    service = AppointmentService(session)
    appointment = await service.create(payload.model_dump())
    return success({"id": appointment.id, "status": appointment.status})
