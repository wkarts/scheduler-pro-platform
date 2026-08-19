from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import text

from app.db.session import PlatformSession, tenant_session
from app.services.observability_service import ObservabilityService
from app.services.tenant_resolver import TenantResolver

_SKIP_SUCCESS_PATHS = {
    "/api/v1/health",
    "/api/v1/health/live",
    "/api/v1/health/ready",
}
_platform_schema_ready = False
_platform_schema_lock = asyncio.Lock()


def _hostname(value: str) -> str:
    clean = value.strip().lower()
    if clean.startswith("[") and "]" in clean:
        return clean[1 : clean.index("]")]
    return clean.split(":", 1)[0].rstrip(".")


def _level(status_code: int) -> str:
    if status_code >= 500:
        return "ERROR"
    if status_code >= 400:
        return "WARNING"
    return "INFO"


async def _ensure_platform_schema_once(session: Any) -> None:
    global _platform_schema_ready
    if _platform_schema_ready:
        return
    async with _platform_schema_lock:
        if _platform_schema_ready:
            return
        await ObservabilityService(session).ensure_platform_schema()
        _platform_schema_ready = True


async def _write_tenant_copy(
    *,
    platform_session: Any,
    tenant_id: str,
    level: str,
    message: str,
    correlation_id: str,
    request_id: str,
    actor: str | None,
    error_code: str | None,
    details_json: str,
) -> None:
    context = await TenantResolver(platform_session).resolve_by_id(
        tenant_id,
        require_active=False,
    )
    async for tenant_db in tenant_session(context):
        await tenant_db.execute(
            text(
                """
                insert into tenant_log_entries(
                  source, service, level, event, message,
                  correlation_id, request_id, actor, integration,
                  error_code, details
                ) values(
                  'http', 'scheduler-api', :level, 'http_request', :message,
                  :correlation_id, :request_id, :actor, null,
                  :error_code, cast(:details as jsonb)
                )
                """
            ),
            {
                "level": level,
                "message": message,
                "correlation_id": correlation_id,
                "request_id": request_id,
                "actor": actor,
                "error_code": error_code,
                "details": details_json,
            },
        )
        await tenant_db.commit()
        break


async def persist_http_operation(
    *,
    method: str,
    path: str,
    query: str | None,
    status_code: int,
    duration_ms: float,
    request_id: str,
    correlation_id: str,
    host: str,
    client_ip: str | None,
    user_agent: str | None,
    principal: dict[str, Any] | None = None,
    error_type: str | None = None,
) -> None:
    """Persist a safe request trace in platform and tenant history.

    Request bodies, authorization headers, cookies and secrets are deliberately
    excluded. Tenant requests are mirrored into the isolated tenant database so
    the Control Plane can show an individual history even after Docker rotates.
    """

    if status_code < 400 and path in _SKIP_SUCCESS_PATHS:
        return
    if status_code < 400 and path == "/api/v1/realtime/events":
        return

    principal = principal or {}
    tenant_id = str(principal.get("tenant_id") or "").strip() or None
    clean_host = _hostname(host)
    level = _level(status_code)
    error_code = error_type if status_code >= 500 else None
    details = {
        "method": method,
        "path": path,
        "query": query,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "client_ip": client_ip,
        "user_agent": (user_agent or "")[:240] or None,
        "user_type": principal.get("user_type"),
        "session_id": principal.get("session_id"),
        "error_type": error_type,
        "hostname": clean_host or None,
    }
    details_json = json.dumps(details, ensure_ascii=False, default=str)
    message = f"{method} {path} → HTTP {status_code}"

    try:
        async with PlatformSession() as session:
            await _ensure_platform_schema_once(session)
            if tenant_id is None and clean_host:
                tenant_id = await session.scalar(
                    text(
                        """
                        select tenant_id::text
                        from domains
                        where lower(hostname)=:hostname
                        order by is_primary desc, is_temporary desc
                        limit 1
                        """
                    ),
                    {"hostname": clean_host},
                )
                tenant_id = str(tenant_id) if tenant_id else None

            await session.execute(
                text(
                    """
                    insert into platform_log_entries(
                      tenant_id, source, service, level, event, message,
                      correlation_id, request_id, actor, hostname,
                      integration, error_code, details
                    ) values(
                      cast(:tenant_id as uuid), 'http', 'scheduler-api', :level,
                      'http_request', :message, :correlation_id, :request_id,
                      :actor, :hostname, null, :error_code, cast(:details as jsonb)
                    )
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "level": level,
                    "message": message,
                    "correlation_id": correlation_id,
                    "request_id": request_id,
                    "actor": principal.get("user_id"),
                    "hostname": clean_host or None,
                    "error_code": error_code,
                    "details": details_json,
                },
            )
            await session.commit()

            if tenant_id:
                await _write_tenant_copy(
                    platform_session=session,
                    tenant_id=tenant_id,
                    level=level,
                    message=message,
                    correlation_id=correlation_id,
                    request_id=request_id,
                    actor=str(principal.get("user_id") or "") or None,
                    error_code=error_code,
                    details_json=details_json,
                )
    except Exception:
        # Observability is fail-open: a logging outage must never take down the API.
        return
