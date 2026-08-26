from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_platform_login_stage_user,
    get_platform_session,
    get_tenant_login_stage_user,
    get_tenant_session,
)
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.services.two_factor_service import TwoFactorService

router = APIRouter()


class TwoFactorCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


async def _audit_platform(
    session: AsyncSession,
    request: Request,
    principal: AuthPrincipal,
    action: str,
    result: str,
) -> None:
    await session.execute(
        text(
            """
            insert into platform_audit_logs(
                user_id, action, result, ip_address, correlation_id, metadata
            ) values(
                cast(:user_id as uuid), :action, :result, :ip, :correlation_id,
                cast(:metadata as jsonb)
            )
            """
        ),
        {
            "user_id": principal.user_id,
            "action": action,
            "result": result,
            "ip": request.client.host if request.client else None,
            "correlation_id": getattr(request.state, "correlation_id", None),
            "metadata": json.dumps({"second_factor": True}),
        },
    )


async def _audit_tenant(
    session: AsyncSession,
    request: Request,
    principal: AuthPrincipal,
    action: str,
    result: str,
) -> None:
    await session.execute(
        text(
            """
            insert into audit_logs(
                user_id, action, result, ip_address, correlation_id, metadata
            ) values(
                cast(:user_id as uuid), :action, :result, :ip, :correlation_id,
                cast(:metadata as jsonb)
            )
            """
        ),
        {
            "user_id": principal.user_id,
            "action": action,
            "result": result,
            "ip": request.client.host if request.client else None,
            "correlation_id": getattr(request.state, "correlation_id", None),
            "metadata": json.dumps({"second_factor": True}),
        },
    )


def _state_payload(state: Any) -> dict[str, Any]:
    return {
        "enabled": bool(state.enabled),
        "configured": bool(state.configured),
        "mandatory": bool(state.mandatory),
        "second_factor_verified": bool(state.second_factor_verified),
    }


@router.get("/platform/2fa/state")
async def platform_two_factor_state(
    principal: AuthPrincipal = Depends(get_platform_login_stage_user),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    state = await TwoFactorService.platform(session).state(
        principal.user_id,
        principal.session_id,
    )
    return success(_state_payload(state))


@router.post("/platform/2fa/setup")
async def platform_two_factor_setup(
    request: Request,
    principal: AuthPrincipal = Depends(get_platform_login_stage_user),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = TwoFactorService.platform(session)
    state = await service.state(principal.user_id, principal.session_id)
    if state.enabled:
        raise APIError(
            "AUTH_SECOND_FACTOR_ALREADY_ENABLED",
            "A verificação em duas etapas já está configurada.",
            409,
        )
    enrollment = await service.begin_enrollment(
        user_id=principal.user_id,
        email=principal.email,
    )
    await _audit_platform(session, request, principal, "auth.2fa.setup", "PENDING")
    await session.commit()
    return success(enrollment)


@router.post("/platform/2fa/confirm")
async def platform_two_factor_confirm(
    payload: TwoFactorCodeRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_platform_login_stage_user),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = TwoFactorService.platform(session)
    try:
        await service.confirm_enrollment(
            user_id=principal.user_id,
            session_id=principal.session_id,
            code=payload.code,
        )
    except APIError:
        await _audit_platform(session, request, principal, "auth.2fa.confirm", "DENIED")
        await session.commit()
        raise
    await _audit_platform(session, request, principal, "auth.2fa.confirm", "SUCCESS")
    await session.commit()
    return success({"verified": True, "mandatory": True})


@router.post("/platform/2fa/verify")
async def platform_two_factor_verify(
    payload: TwoFactorCodeRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_platform_login_stage_user),
    session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    service = TwoFactorService.platform(session)
    try:
        await service.verify_session(
            user_id=principal.user_id,
            session_id=principal.session_id,
            code=payload.code,
        )
    except APIError:
        await _audit_platform(session, request, principal, "auth.2fa.verify", "DENIED")
        await session.commit()
        raise
    await _audit_platform(session, request, principal, "auth.2fa.verify", "SUCCESS")
    await session.commit()
    return success({"verified": True, "mandatory": True})


@router.get("/2fa/state")
async def tenant_two_factor_state(
    principal: AuthPrincipal = Depends(get_tenant_login_stage_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    state = await TwoFactorService.tenant(session).state(
        principal.user_id,
        principal.session_id,
    )
    return success(_state_payload(state))


@router.post("/2fa/setup")
async def tenant_two_factor_setup(
    request: Request,
    principal: AuthPrincipal = Depends(get_tenant_login_stage_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = TwoFactorService.tenant(session)
    state = await service.state(principal.user_id, principal.session_id)
    if state.enabled:
        raise APIError(
            "AUTH_SECOND_FACTOR_ALREADY_ENABLED",
            "A verificação em duas etapas já está configurada.",
            409,
        )
    enrollment = await service.begin_enrollment(
        user_id=principal.user_id,
        email=principal.email,
    )
    await _audit_tenant(session, request, principal, "auth.2fa.setup", "PENDING")
    await session.commit()
    return success(enrollment)


@router.post("/2fa/confirm")
async def tenant_two_factor_confirm(
    payload: TwoFactorCodeRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_tenant_login_stage_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = TwoFactorService.tenant(session)
    try:
        await service.confirm_enrollment(
            user_id=principal.user_id,
            session_id=principal.session_id,
            code=payload.code,
        )
    except APIError:
        await _audit_tenant(session, request, principal, "auth.2fa.confirm", "DENIED")
        await session.commit()
        raise
    await _audit_tenant(session, request, principal, "auth.2fa.confirm", "SUCCESS")
    await session.commit()
    return success({"verified": True, "mandatory": False})


@router.post("/2fa/verify")
async def tenant_two_factor_verify(
    payload: TwoFactorCodeRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_tenant_login_stage_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    service = TwoFactorService.tenant(session)
    try:
        await service.verify_session(
            user_id=principal.user_id,
            session_id=principal.session_id,
            code=payload.code,
        )
    except APIError:
        await _audit_tenant(session, request, principal, "auth.2fa.verify", "DENIED")
        await session.commit()
        raise
    await _audit_tenant(session, request, principal, "auth.2fa.verify", "SUCCESS")
    await session.commit()
    return success({"verified": True, "mandatory": False})


@router.post("/2fa/disable")
async def tenant_two_factor_disable(
    payload: TwoFactorCodeRequest,
    request: Request,
    principal: AuthPrincipal = Depends(get_tenant_login_stage_user),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    await TwoFactorService.tenant(session).disable_tenant(
        user_id=principal.user_id,
        code=payload.code,
    )
    await _audit_tenant(session, request, principal, "auth.2fa.disable", "SUCCESS")
    await session.commit()
    return success({"enabled": False})
