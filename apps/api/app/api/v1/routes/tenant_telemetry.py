import json
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_tenant_user,
    get_platform_session,
    get_tenant_context,
    get_tenant_session,
)
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.observability_service import ObservabilityService

router = APIRouter()
_SENSITIVE = ("password", "passwd", "token", "authorization", "cookie", "secret", "api_key", "apikey")


class TenantTelemetryEvent(BaseModel):
    level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    event: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=1, max_length=2000)
    details: dict[str, Any] = Field(default_factory=dict)


def _redact(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[truncated]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:80]:
            lowered = str(key).lower()
            if any(sensitive in lowered for sensitive in _SENSITIVE):
                result[str(key)] = "[redacted]"
            else:
                result[str(key)] = _redact(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [_redact(item, depth=depth + 1) for item in value[:80]]
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:1000]


@router.post("/events")
async def ingest_tenant_frontend_event(
    payload: TenantTelemetryEvent,
    principal: AuthPrincipal = Depends(get_current_tenant_user),
    context: TenantContext = Depends(get_tenant_context),
    tenant_db: AsyncSession = Depends(get_tenant_session),
    platform_db: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    details = _redact(payload.details)
    details_json = json.dumps(details, ensure_ascii=False, default=str)

    await ObservabilityService(tenant_db).ensure_tenant_schema()
    await tenant_db.execute(
        text(
            """
            insert into tenant_log_entries(
              source, service, level, event, message,
              actor, integration, details
            ) values(
              'frontend', 'tenant-web', :level, :event, :message,
              :actor, 'browser', cast(:details as jsonb)
            )
            """
        ),
        {
            "level": payload.level,
            "event": payload.event,
            "message": payload.message,
            "actor": principal.email,
            "details": details_json,
        },
    )
    await tenant_db.commit()

    await ObservabilityService(platform_db).record_platform_log(
        tenant_id=context.tenant_id,
        source="frontend",
        service="tenant-web",
        level=payload.level,
        event=payload.event,
        message=payload.message,
        actor=principal.email,
        hostname=context.hostname,
        integration="browser",
        details=details,
        commit=True,
    )
    return success({"accepted": True})
