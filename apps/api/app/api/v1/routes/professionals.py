from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.errors import APIError
from app.core.responses import success
from app.db.models_tenant import Appointment, Professional

router = APIRouter()


class ProfessionalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)


class ProfessionalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)


def _row(professional: Professional) -> dict[str, Any]:
    return {"id": professional.id, "name": professional.name, "email": professional.email, "phone": professional.phone}


async def _get(session: AsyncSession, professional_id: str) -> Professional:
    professional = await session.get(Professional, professional_id)
    if professional is None:
        raise APIError("PROFESSIONAL_NOT_FOUND", "Profissional não encontrado.", 404)
    return professional


@router.get("")
async def list_professionals(session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    result = await session.execute(select(Professional).order_by(Professional.name))
    return success([_row(professional) for professional in result.scalars()])


@router.get("/{professional_id}")
async def get_professional(professional_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    return success(_row(await _get(session, professional_id)))


@router.post("")
async def create_professional(payload: ProfessionalCreate, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    professional = Professional(name=payload.name, email=str(payload.email) if payload.email else None, phone=payload.phone)
    session.add(professional)
    await session.commit()
    await session.refresh(professional)
    return success(_row(professional))


@router.patch("/{professional_id}")
async def update_professional(professional_id: str, payload: ProfessionalUpdate, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    professional = await _get(session, professional_id)
    values = payload.model_dump(exclude_unset=True)
    if "email" in values and values["email"] is not None:
        values["email"] = str(values["email"])
    for key, value in values.items():
        setattr(professional, key, value)
    await session.commit()
    await session.refresh(professional)
    return success(_row(professional))


@router.delete("/{professional_id}")
async def delete_professional(professional_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    await _get(session, professional_id)
    appointment = await session.scalar(select(Appointment.id).where(Appointment.professional_id == professional_id).limit(1))
    if appointment:
        raise APIError("PROFESSIONAL_HAS_APPOINTMENTS", "Profissional possui agendamentos e não pode ser excluído.", 409)
    await session.execute(delete(Professional).where(Professional.id == professional_id))
    await session.commit()
    return success({"deleted": True, "id": professional_id})
