from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session, require_permission
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.db.models_tenant import Customer

router = APIRouter()


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=4000)


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=4000)


def _row(customer: Customer) -> dict[str, Any]:
    return {"id": customer.id, "name": customer.name, "phone": customer.phone, "email": customer.email, "notes": customer.notes, "created_at": customer.created_at}


async def _get(session: AsyncSession, customer_id: str) -> Customer:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise APIError("CUSTOMER_NOT_FOUND", "Cliente não encontrado.", 404)
    return customer


@router.get("")
async def list_customers(
    _: AuthPrincipal = Depends(require_permission("customers.read")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    result = await session.execute(select(Customer).order_by(Customer.created_at.desc()).limit(500))
    return success([_row(customer) for customer in result.scalars()])


@router.get("/{customer_id}")
async def get_customer(
    customer_id: str,
    _: AuthPrincipal = Depends(require_permission("customers.read")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(_row(await _get(session, customer_id)))


@router.post("")
async def create_customer(
    payload: CustomerCreate,
    _: AuthPrincipal = Depends(require_permission("customers.manage")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    customer = Customer(name=payload.name, phone=payload.phone, email=str(payload.email) if payload.email else None, notes=payload.notes)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return success(_row(customer))


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    _: AuthPrincipal = Depends(require_permission("customers.manage")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    customer = await _get(session, customer_id)
    values = payload.model_dump(exclude_unset=True)
    if "email" in values and values["email"] is not None:
        values["email"] = str(values["email"])
    for key, value in values.items():
        setattr(customer, key, value)
    await session.commit()
    await session.refresh(customer)
    return success(_row(customer))


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: str,
    _: AuthPrincipal = Depends(require_permission("customers.manage")),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    await _get(session, customer_id)
    from app.db.models_tenant import Appointment

    appointments = await session.scalar(select(Appointment.id).where(Appointment.customer_id == customer_id).limit(1))
    if appointments:
        raise APIError("CUSTOMER_HAS_APPOINTMENTS", "Cliente possui agendamentos e não pode ser excluído.", 409)
    await session.execute(delete(Customer).where(Customer.id == customer_id))
    await session.commit()
    return success({"deleted": True, "id": customer_id})
