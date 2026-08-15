from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.responses import success
from app.db.models_tenant import Professional

router = APIRouter()


class ProfessionalCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None


@router.get("")
async def list_professionals(session: AsyncSession = Depends(get_tenant_session)):
    result = await session.execute(select(Professional).order_by(Professional.name))
    return success([{"id": p.id, "name": p.name, "email": p.email, "phone": p.phone} for p in result.scalars()])


@router.post("")
async def create_professional(payload: ProfessionalCreate, session: AsyncSession = Depends(get_tenant_session)):
    professional = Professional(name=payload.name, email=payload.email, phone=payload.phone)
    session.add(professional)
    await session.commit()
    await session.refresh(professional)
    return success({"id": professional.id, "name": professional.name})
