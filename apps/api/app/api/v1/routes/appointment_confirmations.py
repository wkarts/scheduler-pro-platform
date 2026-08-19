from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.appointment_confirmation_service import AppointmentConfirmationService

router = APIRouter()


def _public_base_url(context: TenantContext) -> str:
    scheme = "http" if context.hostname in {"localhost", "127.0.0.1"} else "https"
    return f"{scheme}://{context.hostname}"


@router.get("/{appointment_id}")
async def confirmation_link(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = AppointmentConfirmationService(session)
    request = await service.ensure_request(
        appointment_id,
        public_base_url=_public_base_url(context),
    )
    await session.commit()
    return success(
        {
            "enabled": request is not None,
            "request": request,
            "preferences": await service.notification_preferences(),
        }
    )


@router.post("/{appointment_id}/regenerate")
async def regenerate_confirmation_link(
    appointment_id: str,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = AppointmentConfirmationService(session)
    request = await service.ensure_request(
        appointment_id,
        public_base_url=_public_base_url(context),
        rotate=True,
    )
    await session.commit()
    return success({"enabled": request is not None, "request": request})
