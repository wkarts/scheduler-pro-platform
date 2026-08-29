from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.errors import APIError
from app.core.responses import success
from app.db.models_tenant import Appointment, Service

router = APIRouter()


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    duration_minutes: int = Field(default=30, ge=0, le=720)
    price: float | None = Field(default=None, ge=0)
    active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    duration_minutes: int | None = Field(default=None, ge=0, le=720)
    price: float | None = Field(default=None, ge=0)
    active: bool | None = None


def _row(service: Service) -> dict[str, Any]:
    return {"id": service.id, "name": service.name, "duration_minutes": service.duration_minutes, "price": float(service.price) if service.price is not None else None, "active": str(service.active).lower() == "true"}


async def _get(session: AsyncSession, service_id: str) -> Service:
    service = await session.get(Service, service_id)
    if service is None:
        raise APIError("SERVICE_NOT_FOUND", "Serviço não encontrado.", 404)
    return service


@router.get("")
async def list_services(session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    result = await session.execute(select(Service).order_by(Service.name))
    return success([_row(service) for service in result.scalars()])


@router.get("/{service_id}")
async def get_service(service_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return success(_row(await _get(session, service_id)))


@router.post("")
async def create_service(payload: ServiceCreate, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    service = Service(name=payload.name, duration_minutes=payload.duration_minutes, price=payload.price, active="true" if payload.active else "false")
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return success(_row(service))


@router.patch("/{service_id}")
async def update_service(service_id: str, payload: ServiceUpdate, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    service = await _get(session, service_id)
    values = payload.model_dump(exclude_unset=True)
    if "active" in values:
        values["active"] = "true" if values["active"] else "false"
    for key, value in values.items():
        setattr(service, key, value)
    await session.commit()
    await session.refresh(service)
    return success(_row(service))


@router.delete("/{service_id}")
async def delete_service(service_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    await _get(session, service_id)
    appointment = await session.scalar(select(Appointment.id).where(Appointment.service_id == service_id).limit(1))
    if appointment:
        raise APIError("SERVICE_HAS_APPOINTMENTS", "Serviço possui agendamentos; desative em vez de excluir.", 409)
    await session.execute(delete(Service).where(Service.id == service_id))
    await session.commit()
    return success({"deleted": True, "id": service_id})
