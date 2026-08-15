from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session, require_permission
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.db.models_tenant import Customer

router = APIRouter()


class CustomerCreate(BaseModel):
    name: str
    phone: str | None = None
    email: EmailStr | None = None


@router.get("")
async def list_customers(
    _: AuthPrincipal = Depends(require_permission("customers.read")),
    session: AsyncSession = Depends(get_tenant_session),
):
    result = await session.execute(
        select(Customer).order_by(Customer.created_at.desc()).limit(100)
    )
    return success(
        [
            {"id": c.id, "name": c.name, "phone": c.phone, "email": c.email}
            for c in result.scalars()
        ]
    )


@router.post("")
async def create_customer(
    payload: CustomerCreate,
    _: AuthPrincipal = Depends(require_permission("customers.manage")),
    session: AsyncSession = Depends(get_tenant_session),
):
    customer = Customer(
        name=payload.name,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return success({"id": customer.id, "name": customer.name})
