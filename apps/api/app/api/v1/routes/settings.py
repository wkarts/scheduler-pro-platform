import json
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_platform_session,
    get_tenant_context,
    get_tenant_session,
)
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.booking_parameters_service import BookingParametersService

router = APIRouter()


class SimultaneousSettings(BaseModel):
    public: bool = False
    internal: bool = False
    capacity: int = Field(default=1, ge=1, le=10000)
    enforce_public: bool = True
    enforce_internal: bool = True


class BookingRuleSettings(BaseModel):
    enforce_business_hours: bool = True
    enforce_blocked_periods: bool = True


class PhoneSettings(BaseModel):
    country: str = Field(default="BR", min_length=2, max_length=3)
    country_code: str = Field(default="55", min_length=1, max_length=8)
    area_code: str = Field(default="", max_length=8)
    add_ninth_digit: bool = True


class BookingParametersUpdate(BaseModel):
    service_mode: str = "REQUIRED"
    email_mode: str = "OPTIONAL"
    phone_mode: str = "REQUIRED"
    duration_mode: str = "REQUIRED"
    professional_mode: str = "REQUIRED"
    default_duration_minutes: int = Field(default=60, ge=5, le=720)
    default_professional_name: str = Field(default="Agenda geral", min_length=2, max_length=160)
    default_customer_mode: str = "NEW"
    simultaneous: SimultaneousSettings = Field(default_factory=SimultaneousSettings)
    rules: BookingRuleSettings = Field(default_factory=BookingRuleSettings)
    minimum_notice_minutes: int = Field(default=1440, ge=0, le=525600)
    phone: PhoneSettings = Field(default_factory=PhoneSettings)


@router.get("/tenant")
async def tenant_settings(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            text("select key, value, updated_at from tenant_settings order by key")
        )
    ).mappings().all()
    return success(
        {
            "tenant_id": context.tenant_id,
            "slug": context.slug,
            "hostname": context.hostname,
            "timezone": context.timezone,
            "preferences": {row["key"]: row["value"] for row in rows},
        }
    )


@router.get("/booking")
async def booking_parameters(
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await BookingParametersService(session).get())


@router.put("/booking")
async def update_booking_parameters(
    payload: BookingParametersUpdate,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(
        await BookingParametersService(session).update(payload.model_dump())
    )


@router.get("/capabilities")
async def tenant_capabilities(
    context: TenantContext = Depends(get_tenant_context),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    rows = (
        await platform_session.execute(
            text(
                """
                select capability_key as key, enabled, config, updated_at
                from tenant_capabilities
                where tenant_id=cast(:tenant_id as uuid)
                order by capability_key
                """
            ),
            {"tenant_id": context.tenant_id},
        )
    ).mappings().all()
    return success(
        {
            "tenant_id": context.tenant_id,
            "enabled": [row["key"] for row in rows if row["enabled"]],
            "capabilities": [dict(row) for row in rows],
        }
    )


@router.put("/tenant/{key}")
async def update_tenant_setting(
    key: str,
    value: Any = Body(...),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    clean_key = key.strip().lower().replace(" ", "_")
    if (
        not clean_key
        or len(clean_key) > 120
        or not clean_key.replace("_", "").replace("-", "").isalnum()
    ):
        from app.core.errors import APIError

        raise APIError("SETTING_KEY_INVALID", "Chave de configuração inválida.", 422)
    await session.execute(
        text(
            """
            insert into tenant_settings(key, value, updated_at)
            values(:key, cast(:value as jsonb), now())
            on conflict(key) do update set value=excluded.value, updated_at=now()
            """
        ),
        {
            "key": clean_key,
            "value": json.dumps(value, ensure_ascii=False, default=str),
        },
    )
    await session.commit()
    return success({"key": clean_key, "value": value})
