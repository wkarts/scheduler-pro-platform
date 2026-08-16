import json
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.responses import success
from app.core.tenant_context import TenantContext

router = APIRouter()


@router.get("/tenant")
async def tenant_settings(
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    rows = (
        await session.execute(text("select key, value, updated_at from tenant_settings order by key"))
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


@router.put("/tenant/{key}")
async def update_tenant_setting(
    key: str,
    value: Any = Body(...),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    clean_key = key.strip().lower().replace(" ", "_")
    if not clean_key or len(clean_key) > 120 or not clean_key.replace("_", "").replace("-", "").isalnum():
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
        {"key": clean_key, "value": json.dumps(value, ensure_ascii=False, default=str)},
    )
    await session.commit()
    return success({"key": clean_key, "value": value})
