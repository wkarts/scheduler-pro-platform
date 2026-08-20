from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.api.v1.routes.appointments import _publish_realtime, _public_base_url
from app.core.errors import APIError
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.appointment_service import AppointmentService, FINAL_STATUSES
from app.services.notification_service import NotificationService

router = APIRouter()


class AppointmentSmartEdit(BaseModel):
    customer_id: str | None = None
    service_id: str | None = None
    professional_id: str | None = None
    starts_at: datetime | None = None
    reason: str | None = Field(default="Dados atualizados pelo gestor", max_length=500)


@router.get("/smart/lookups")
async def smart_appointment_lookups(
    q: str = Query(default="", max_length=160),
    limit: int = Query(default=100, ge=1, le=250),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    """Lookup da Agenda, independente dos CRUDs opcionais de clientes/serviços/equipe."""
    needle = f"%{q.strip()}%"
    customers = (
        await session.execute(
            text(
                """
                select id::text, name, phone, email
                from customers
                where :q = '%%'
                   or name ilike :q
                   or coalesce(phone, '') ilike :q
                   or coalesce(email, '') ilike :q
                order by name
                limit :limit
                """
            ),
            {"q": needle, "limit": limit},
        )
    ).mappings().all()
    services = (
        await session.execute(
            text(
                """
                select id::text, name, duration_minutes, price, active
                from services
                where lower(coalesce(active::text, '')) in ('true', 't', '1', 'yes', 'on', 'active', 'enabled')
                  and (:q = '%%' or name ilike :q)
                order by name
                limit :limit
                """
            ),
            {"q": needle, "limit": limit},
        )
    ).mappings().all()
    professionals = (
        await session.execute(
            text(
                """
                select id::text, name, email, phone
                from professionals
                where :q = '%%'
                   or name ilike :q
                   or coalesce(email, '') ilike :q
                   or coalesce(phone, '') ilike :q
                order by name
                limit :limit
                """
            ),
            {"q": needle, "limit": limit},
        )
    ).mappings().all()
    return success(
        {
            "customers": [dict(row) for row in customers],
            "services": [dict(row) for row in services],
            "professionals": [dict(row) for row in professionals],
        }
    )


@router.patch("/{appointment_id}/edit")
async def edit_appointment(
    appointment_id: str,
    payload: AppointmentSmartEdit,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = AppointmentService(
        session,
        public_base_url=_public_base_url(context),
        timezone=context.timezone,
    )
    current = await service.get(appointment_id)
    if str(current["status"]) in FINAL_STATUSES:
        raise APIError(
            "APPOINTMENT_EDIT_FINAL",
            "Agendamentos concluídos, cancelados ou faltas não podem ser editados. Use reutilizar ou crie um novo atendimento.",
            409,
        )

    customer_id = payload.customer_id or str(current["customer_id"])
    service_id = payload.service_id or str(current["service_id"])
    professional_id = payload.professional_id or str(current["professional_id"])
    starts_at = payload.starts_at or current["starts_at"]

    await service._require_reference("customers", customer_id, "CUSTOMER_NOT_FOUND")
    await service._require_reference("services", service_id, "SERVICE_NOT_FOUND")
    await service._require_reference("professionals", professional_id, "PROFESSIONAL_NOT_FOUND")

    service_row = (
        await session.execute(
            text(
                """
                select duration_minutes, active
                from services
                where id=cast(:id as uuid)
                """
            ),
            {"id": service_id},
        )
    ).mappings().first()
    if service_row is None:
        raise APIError("SERVICE_NOT_FOUND", "Serviço não encontrado.", 404)
    duration_minutes = int(service_row["duration_minutes"] or 30)
    ends_at = starts_at + timedelta(minutes=duration_minutes)

    slot_changed = (
        professional_id != str(current["professional_id"])
        or starts_at != current["starts_at"]
        or ends_at != current["ends_at"]
    )
    if slot_changed:
        await service._ensure_slot_available(
            professional_id,
            starts_at,
            ends_at,
            ignore_appointment_id=appointment_id,
        )

    next_status = "AWAITING_CONFIRMATION" if slot_changed else str(current["status"])
    await session.execute(
        text(
            """
            update appointments
            set customer_id=cast(:customer_id as uuid),
                service_id=cast(:service_id as uuid),
                professional_id=cast(:professional_id as uuid),
                starts_at=:starts_at,
                ends_at=:ends_at,
                status=:status
            where id=cast(:id as uuid)
            """
        ),
        {
            "id": appointment_id,
            "customer_id": customer_id,
            "service_id": service_id,
            "professional_id": professional_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
            "status": next_status,
        },
    )
    reason = payload.reason or "Dados atualizados pelo gestor"
    await service._add_history(appointment_id, next_status, reason)

    if slot_changed:
        await NotificationService(
            session,
            public_base_url=_public_base_url(context),
        ).schedule_for_appointment(
            appointment_id,
            "appointment_rescheduled",
            reason=reason,
            rotate_confirmation=True,
        )

    await session.commit()
    updated = await service.get(appointment_id)
    await _publish_realtime(
        context,
        session,
        appointment_id,
        "appointment.rescheduled" if slot_changed else "appointment.updated",
        extra={"smart_edit": True},
    )
    return success(updated)
