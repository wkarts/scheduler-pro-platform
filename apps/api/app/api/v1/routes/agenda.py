from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.api.v1.routes.appointments import _publish_realtime, _public_base_url
from app.core.errors import APIError
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.booking_parameters_service import BookingParametersService
from app.services.flexible_appointment_service import FlexibleAppointmentService
from app.services.phone_normalization import PhoneNormalizationService

router = APIRouter()


class FlexibleQuickCreate(BaseModel):
    starts_at: datetime
    customer_id: str | None = None
    customer_name: str = Field(min_length=2, max_length=160)
    customer_phone: str | None = Field(default=None, max_length=80)
    customer_email: EmailStr | None = None
    confirm_customer_update: bool = False
    service_id: str | None = None
    service_name: str | None = Field(default=None, max_length=160)
    duration_minutes: int | None = Field(default=None, ge=5, le=720)
    price: float | None = Field(default=None, ge=0)
    professional_id: str | None = None
    professional_name: str | None = Field(default=None, max_length=160)
    source: str = Field(default="tenant-web-flexible", max_length=40)


class ReportScheduleUpdate(BaseModel):
    enabled: bool = False
    period: Literal["day", "week", "month", "quarter", "semester", "year"] = "month"
    delivery_channels: list[Literal["email", "whatsapp"]] = Field(default_factory=list)
    email: EmailStr | None = None
    whatsapp: str | None = Field(default=None, max_length=80)
    format: Literal["link", "pdf", "link_pdf"] = "link"
    hour: int = Field(default=8, ge=0, le=23)


class ReportScheduleEnvelope(BaseModel):
    schedules: list[ReportScheduleUpdate] = Field(default_factory=list, max_length=12)


def _timezone(context: TenantContext) -> ZoneInfo:
    try:
        return ZoneInfo(context.timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/Bahia")


def _period_bounds(
    period: str,
    anchor: date,
    timezone: ZoneInfo,
) -> tuple[datetime, datetime]:
    if period == "day":
        start_date = anchor
        end_date = anchor + timedelta(days=1)
    elif period == "week":
        start_date = anchor - timedelta(days=anchor.weekday())
        end_date = start_date + timedelta(days=7)
    elif period == "month":
        start_date = anchor.replace(day=1)
        end_date = (
            start_date.replace(year=start_date.year + 1, month=1)
            if start_date.month == 12
            else start_date.replace(month=start_date.month + 1)
        )
    elif period == "quarter":
        month = ((anchor.month - 1) // 3) * 3 + 1
        start_date = anchor.replace(month=month, day=1)
        next_month = month + 3
        end_date = (
            start_date.replace(year=start_date.year + 1, month=next_month - 12)
            if next_month > 12
            else start_date.replace(month=next_month)
        )
    elif period == "semester":
        month = 1 if anchor.month <= 6 else 7
        start_date = anchor.replace(month=month, day=1)
        end_date = (
            start_date.replace(month=7)
            if month == 1
            else start_date.replace(year=start_date.year + 1, month=1)
        )
    elif period == "year":
        start_date = anchor.replace(month=1, day=1)
        end_date = start_date.replace(year=start_date.year + 1)
    else:
        raise APIError("AGENDA_REPORT_PERIOD_INVALID", "Período de relatório inválido.", 422)
    start = datetime.combine(start_date, time.min, tzinfo=timezone).astimezone(UTC)
    end = datetime.combine(end_date, time.min, tzinfo=timezone).astimezone(UTC)
    return start, end


async def _resolve_customer(
    session: AsyncSession,
    payload: FlexibleQuickCreate,
    params: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    if payload.customer_id:
        exists = await session.scalar(
            text("select exists(select 1 from customers where id=cast(:id as uuid))"),
            {"id": payload.customer_id},
        )
        if not exists:
            raise APIError("CUSTOMER_NOT_FOUND", "Cliente não encontrado.", 404)
        return payload.customer_id, None

    phone_mode = str(params.get("phone_mode") or "REQUIRED").upper()
    raw_phone = str(payload.customer_phone or "").strip()
    if not raw_phone:
        if phone_mode == "REQUIRED":
            raise APIError(
                "APPOINTMENT_CUSTOMER_PHONE_REQUIRED",
                "Informe o telefone/WhatsApp do cliente.",
                422,
            )
        customer_id = await session.scalar(
            text(
                """
                insert into customers(name, phone, phone_normalized, email, notes)
                values(:name, null, null, :email,
                       'Criado automaticamente pelo Operador da Agenda')
                returning id::text
                """
            ),
            {
                "name": payload.customer_name.strip(),
                "email": str(payload.customer_email) if payload.customer_email else None,
            },
        )
        return str(customer_id), None

    phones = await PhoneNormalizationService.from_session(session)
    canonical = phones.normalize(raw_phone, required=True)
    assert canonical is not None
    await phones.lock_customer_phone(session, canonical)
    row = (
        await session.execute(
            text(
                """
                select id::text, name, email
                from customers
                where coalesce(phone_normalized, phone)=:phone
                limit 1
                """
            ),
            {"phone": canonical},
        )
    ).mappings().first()
    if row is not None:
        existing_name = str(row["name"] or "").strip()
        new_name = payload.customer_name.strip()
        different_name = existing_name.casefold() != new_name.casefold()
        if different_name and not payload.confirm_customer_update:
            raise APIError(
                "CUSTOMER_PHONE_MATCH_NAME_DIFFERS",
                "Este telefone já pertence a um cliente com outro nome. Confirme antes de atualizar o contato.",
                409,
                {
                    "customer_id": str(row["id"]),
                    "existing_name": existing_name,
                    "received_name": new_name,
                    "phone": canonical,
                    "requires_confirmation": True,
                },
            )
        await session.execute(
            text(
                """
                update customers
                set name=case when :update_name then :name else name end,
                    phone=:phone,
                    phone_normalized=:phone,
                    email=case when :email is null then email else :email end
                where id=cast(:id as uuid)
                """
            ),
            {
                "id": str(row["id"]),
                "name": new_name,
                "update_name": bool(different_name and payload.confirm_customer_update),
                "phone": canonical,
                "email": str(payload.customer_email) if payload.customer_email else None,
            },
        )
        return str(row["id"]), {
            "matched_by_phone": True,
            "name_updated": bool(different_name and payload.confirm_customer_update),
            "phone": canonical,
        }

    customer_id = await session.scalar(
        text(
            """
            insert into customers(name, phone, phone_normalized, email, notes)
            values(:name, :phone, :phone, :email,
                   'Criado automaticamente pelo Operador da Agenda')
            returning id::text
            """
        ),
        {
            "name": payload.customer_name.strip(),
            "phone": canonical,
            "email": str(payload.customer_email) if payload.customer_email else None,
        },
    )
    return str(customer_id), {"matched_by_phone": False, "phone": canonical}


async def _resolve_service(
    session: AsyncSession,
    payload: FlexibleQuickCreate,
    engine: FlexibleAppointmentService,
    params: dict[str, Any],
) -> tuple[str | None, int]:
    mode = str(params.get("service_mode") or "REQUIRED").upper()
    default_duration = int(params.get("default_duration_minutes") or 60)
    if mode == "DISABLED":
        return None, default_duration
    if payload.service_id:
        row = (
            await session.execute(
                text("select id::text, duration_minutes from services where id=cast(:id as uuid)"),
                {"id": payload.service_id},
            )
        ).mappings().first()
        if row is None:
            raise APIError("SERVICE_NOT_FOUND", "Serviço não encontrado.", 404)
        return str(row["id"]), int(row["duration_minutes"])
    name = str(payload.service_name or "").strip()
    if not name:
        if mode == "REQUIRED":
            raise APIError("APPOINTMENT_SERVICE_REQUIRED", "Selecione ou informe um serviço.", 422)
        return None, int(payload.duration_minutes or default_duration)
    row = (
        await session.execute(
            text(
                """
                select id::text, duration_minutes
                from services
                where lower(name)=lower(:name) and active='true'
                order by name limit 1
                """
            ),
            {"name": name},
        )
    ).mappings().first()
    if row is not None:
        return str(row["id"]), int(row["duration_minutes"])
    duration = int(payload.duration_minutes or default_duration)
    created = (
        await session.execute(
            text(
                """
                insert into services(name, duration_minutes, price, active)
                values(:name, :duration, :price, 'true')
                returning id::text, duration_minutes
                """
            ),
            {"name": name, "duration": duration, "price": payload.price},
        )
    ).mappings().one()
    return str(created["id"]), int(created["duration_minutes"])


async def _resolve_professional(
    session: AsyncSession,
    payload: FlexibleQuickCreate,
    params: dict[str, Any],
) -> str:
    if payload.professional_id:
        exists = await session.scalar(
            text("select exists(select 1 from professionals where id=cast(:id as uuid))"),
            {"id": payload.professional_id},
        )
        if not exists:
            raise APIError("PROFESSIONAL_NOT_FOUND", "Responsável não encontrado.", 404)
        return payload.professional_id
    name = str(
        payload.professional_name
        or params.get("default_professional_name")
        or "Agenda geral"
    ).strip()
    professional_id = await session.scalar(
        text("select id::text from professionals where lower(name)=lower(:name) limit 1"),
        {"name": name},
    )
    if professional_id:
        return str(professional_id)
    return str(
        await session.scalar(
            text("insert into professionals(name) values(:name) returning id::text"),
            {"name": name},
        )
    )


@router.get("/parameters")
async def agenda_parameters(
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    return success(await BookingParametersService(session).get())


@router.post("/quick")
async def create_flexible_appointment(
    payload: FlexibleQuickCreate,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    params = await BookingParametersService(session).get()
    engine = FlexibleAppointmentService(
        session,
        public_base_url=_public_base_url(context),
        timezone=context.timezone,
    )
    customer_id, customer_resolution = await _resolve_customer(session, payload, params)
    service_id, duration = await _resolve_service(session, payload, engine, params)
    professional_id = await _resolve_professional(session, payload, params)

    duration_mode = str(params.get("duration_mode") or "REQUIRED").upper()
    if duration_mode == "DISABLED":
        duration = int(params.get("default_duration_minutes") or duration or 60)
    elif payload.duration_minutes is not None and service_id is None:
        duration = int(payload.duration_minutes)

    starts_at = payload.starts_at
    ends_at = starts_at + timedelta(minutes=max(5, duration))
    appointment = await engine.create(
        {
            "customer_id": customer_id,
            "service_id": service_id,
            "professional_id": professional_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "source": payload.source,
        }
    )
    appointment_id = str(appointment.id)
    await _publish_realtime(
        context,
        session,
        appointment_id,
        "appointment.created",
        extra={"flexible": True},
    )
    return success(
        {
            "id": appointment_id,
            "status": appointment.status,
            "customer_id": customer_id,
            "service_id": service_id,
            "professional_id": professional_id,
            "customer_resolution": customer_resolution,
        }
    )


@router.get("/reports/summary")
async def agenda_report_summary(
    period: Literal["day", "week", "month", "quarter", "semester", "year"] = Query(default="month"),
    anchor: date | None = Query(default=None),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    timezone = _timezone(context)
    local_anchor = anchor or datetime.now(timezone).date()
    start, end = _period_bounds(period, local_anchor, timezone)
    rows = (
        await session.execute(
            text(
                """
                select a.id::text,
                       a.starts_at,
                       a.status,
                       a.customer_id::text,
                       c.name as customer_name,
                       s.name as service_name,
                       coalesce(s.price, 0) as price,
                       p.name as professional_name
                from appointments a
                join customers c on c.id=a.customer_id
                left join services s on s.id=a.service_id
                join professionals p on p.id=a.professional_id
                where a.starts_at >= :start and a.starts_at < :end
                order by a.starts_at
                """
            ),
            {"start": start, "end": end},
        )
    ).mappings().all()

    statuses: dict[str, int] = {}
    services: dict[str, int] = {}
    professionals: dict[str, int] = {}
    curve: dict[str, int] = {}
    customers: set[str] = set()
    revenue = 0.0
    for row in rows:
        status = str(row["status"])
        statuses[status] = statuses.get(status, 0) + 1
        service_name = str(row["service_name"] or "Sem serviço")
        services[service_name] = services.get(service_name, 0) + 1
        professional_name = str(row["professional_name"] or "Agenda geral")
        professionals[professional_name] = professionals.get(professional_name, 0) + 1
        customers.add(str(row["customer_id"]))
        local_day = row["starts_at"].astimezone(timezone).date().isoformat()
        curve[local_day] = curve.get(local_day, 0) + 1
        if status not in {"CANCELLED", "NO_SHOW"}:
            revenue += float(row["price"] or 0)

    total = len(rows)
    completed = statuses.get("COMPLETED", 0)
    cancelled = statuses.get("CANCELLED", 0)
    no_show = statuses.get("NO_SHOW", 0)
    attendance_base = max(1, total - cancelled)
    return success(
        {
            "period": period,
            "anchor": local_anchor,
            "range": {"starts_at": start, "ends_at": end},
            "synthetic": {
                "appointments": total,
                "unique_customers": len(customers),
                "completed": completed,
                "cancelled": cancelled,
                "no_show": no_show,
                "estimated_revenue": round(revenue, 2),
                "completion_rate": round(completed * 100 / attendance_base, 2),
                "no_show_rate": round(no_show * 100 / attendance_base, 2),
            },
            "analytical": {
                "curve": [{"date": key, "appointments": curve[key]} for key in sorted(curve)],
                "statuses": [
                    {"status": key, "count": value}
                    for key, value in sorted(statuses.items(), key=lambda item: (-item[1], item[0]))
                ],
                "services": [
                    {"name": key, "count": value}
                    for key, value in sorted(services.items(), key=lambda item: (-item[1], item[0]))
                ],
                "professionals": [
                    {"name": key, "count": value}
                    for key, value in sorted(professionals.items(), key=lambda item: (-item[1], item[0]))
                ],
            },
        }
    )


@router.get("/reports/schedules")
async def agenda_report_schedules(
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    value = await session.scalar(
        text("select value from tenant_settings where key='agenda_report_schedules' limit 1")
    )
    return success(value if isinstance(value, list) else [])


@router.put("/reports/schedules")
async def update_agenda_report_schedules(
    payload: ReportScheduleEnvelope,
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    schedules = [item.model_dump(mode="json") for item in payload.schedules]
    await session.execute(
        text(
            """
            insert into tenant_settings(key, value, updated_at)
            values('agenda_report_schedules', cast(:value as jsonb), now())
            on conflict(key) do update set value=excluded.value, updated_at=now()
            """
        ),
        {"value": json.dumps(schedules, ensure_ascii=False)},
    )
    await session.commit()
    return success(schedules)
