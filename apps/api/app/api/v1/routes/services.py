from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.responses import success
from app.db.models_tenant import Service

router = APIRouter()


class ServiceCreate(BaseModel):
    name: str
    duration_minutes: int = Field(default=30, ge=5, le=720)
    price: float | None = None


@router.get("")
async def list_services(session: AsyncSession = Depends(get_tenant_session)):
    result = await session.execute(select(Service).order_by(Service.name))
    return success([{"id": s.id, "name": s.name, "duration_minutes": s.duration_minutes, "price": float(s.price) if s.price is not None else None} for s in result.scalars()])


@router.post("")
async def create_service(payload: ServiceCreate, session: AsyncSession = Depends(get_tenant_session)):
    service = Service(name=payload.name, duration_minutes=payload.duration_minutes, price=payload.price)
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return success({"id": service.id, "name": service.name})
