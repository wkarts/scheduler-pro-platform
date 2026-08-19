from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record_tenant_event(
    session: AsyncSession,
    *,
    source: str,
    service: str,
    event: str,
    message: str,
    level: str = "INFO",
    integration: str | None = None,
    error_code: str | None = None,
    correlation_id: str | None = None,
    request_id: str | None = None,
    actor: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Append a structured event to the tenant-local persistent history.

    This helper intentionally does not commit. It participates in the caller's
    transaction, so business state and its diagnostic event stay consistent.
    """

    await session.execute(
        text(
            """
            insert into tenant_log_entries(
              source, service, level, event, message,
              correlation_id, request_id, actor, integration,
              error_code, details
            ) values(
              :source, :service, :level, :event, :message,
              :correlation_id, :request_id, :actor, :integration,
              :error_code, cast(:details as jsonb)
            )
            """
        ),
        {
            "source": source[:80],
            "service": service[:120],
            "level": level.upper()[:20],
            "event": event[:160],
            "message": message,
            "correlation_id": correlation_id,
            "request_id": request_id,
            "actor": actor,
            "integration": integration,
            "error_code": error_code,
            "details": json.dumps(details or {}, ensure_ascii=False, default=str),
        },
    )
