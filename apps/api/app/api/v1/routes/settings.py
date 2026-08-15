from fastapi import APIRouter, Depends

from app.api.deps import get_tenant_context
from app.core.responses import success
from app.core.tenant_context import TenantContext

router = APIRouter()


@router.get("/tenant")
async def tenant_settings(context: TenantContext = Depends(get_tenant_context)):
    return success({"tenant_id": context.tenant_id, "slug": context.slug, "hostname": context.hostname, "timezone": context.timezone})
