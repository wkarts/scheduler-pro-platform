from datetime import datetime, time
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_session
from app.core.errors import APIError
from app.core.responses import success

router = APIRouter()


class BusinessHourPayload(BaseModel):
    professional_id: str | None = None
    day_of_week: int = Field(ge=0, le=6)
    opens_at: time
    closes_at: time
    is_open: bool = True

    @model_validator(mode="after")
    def validate_interval(self) -> "BusinessHourPayload":
        if self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be greater than opens_at")
        return self


class BlockedPeriodPayload(BaseModel):
    professional_id: str | None = None
    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_interval(self) -> "BlockedPeriodPayload":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be greater than starts_at")
        return self


@router.get("/business-hours")
async def list_business_hours(session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    rows = (
        await session.execute(
            text(
                """
                select bh.id::text, bh.professional_id::text, p.name as professional_name,
                       bh.day_of_week, bh.opens_at, bh.closes_at, bh.is_open, bh.created_at
                from business_hours bh
                left join professionals p on p.id=bh.professional_id
                order by bh.day_of_week, p.name nulls first, bh.opens_at
                """
            )
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.post("/business-hours")
async def create_business_hour(payload: BusinessHourPayload, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    if payload.professional_id:
        exists = await session.scalar(text("select exists(select 1 from professionals where id=:id::uuid)"), {"id": payload.professional_id})
        if not exists:
            raise APIError("PROFESSIONAL_NOT_FOUND", "Profissional não encontrado.", 404)
    row = (
        await session.execute(
            text(
                """
                insert into business_hours(professional_id, day_of_week, opens_at, closes_at, is_open)
                values(cast(:professional_id as uuid), :day_of_week, :opens_at, :closes_at, :is_open)
                returning id::text, professional_id::text, day_of_week, opens_at, closes_at, is_open, created_at
                """
            ),
            payload.model_dump(),
        )
    ).mappings().one()
    await session.commit()
    return success(dict(row))


@router.put("/business-hours/{business_hour_id}")
async def update_business_hour(business_hour_id: str, payload: BusinessHourPayload, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                update business_hours set
                  professional_id=cast(:professional_id as uuid), day_of_week=:day_of_week,
                  opens_at=:opens_at, closes_at=:closes_at, is_open=:is_open
                where id=:id::uuid
                returning id::text, professional_id::text, day_of_week, opens_at, closes_at, is_open, created_at
                """
            ),
            {**payload.model_dump(), "id": business_hour_id},
        )
    ).mappings().first()
    if row is None:
        raise APIError("BUSINESS_HOUR_NOT_FOUND", "Faixa de expediente não encontrada.", 404)
    await session.commit()
    return success(dict(row))


@router.delete("/business-hours/{business_hour_id}")
async def delete_business_hour(business_hour_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    deleted = await session.scalar(text("delete from business_hours where id=:id::uuid returning id::text"), {"id": business_hour_id})
    if not deleted:
        raise APIError("BUSINESS_HOUR_NOT_FOUND", "Faixa de expediente não encontrada.", 404)
    await session.commit()
    return success({"deleted": True, "id": str(deleted)})


@router.get("/blocked-periods")
async def list_blocked_periods(session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    rows = (
        await session.execute(
            text(
                """
                select bp.id::text, bp.professional_id::text, p.name as professional_name,
                       bp.starts_at, bp.ends_at, bp.reason, bp.created_at
                from blocked_periods bp
                left join professionals p on p.id=bp.professional_id
                order by bp.starts_at desc
                limit 500
                """
            )
        )
    ).mappings().all()
    return success([dict(row) for row in rows])


@router.post("/blocked-periods")
async def create_blocked_period(payload: BlockedPeriodPayload, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                insert into blocked_periods(professional_id, starts_at, ends_at, reason)
                values(cast(:professional_id as uuid), :starts_at, :ends_at, :reason)
                returning id::text, professional_id::text, starts_at, ends_at, reason, created_at
                """
            ),
            payload.model_dump(),
        )
    ).mappings().one()
    await session.commit()
    return success(dict(row))


@router.delete("/blocked-periods/{blocked_period_id}")
async def delete_blocked_period(blocked_period_id: str, session: AsyncSession = Depends(get_tenant_session)) -> dict[str, Any]:
    deleted = await session.scalar(text("delete from blocked_periods where id=:id::uuid returning id::text"), {"id": blocked_period_id})
    if not deleted:
        raise APIError("BLOCKED_PERIOD_NOT_FOUND", "Bloqueio não encontrado.", 404)
    await session.commit()
    return success({"deleted": True, "id": str(deleted)})
