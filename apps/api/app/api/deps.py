from collections.abc import AsyncIterator

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import TenantContext
from app.db.session import platform_session, tenant_session
from app.services.tenant_resolver import TenantResolver


async def get_platform_session() -> AsyncIterator[AsyncSession]:
    async for session in platform_session():
        yield session


async def get_tenant_context(request: Request, host: str | None = Header(default=None)) -> TenantContext:
    hostname = (host or request.headers.get("host") or "localhost").split(":")[0].lower()
    async for session in platform_session():
        resolver = TenantResolver(session)
        return await resolver.resolve(hostname)
    raise RuntimeError("platform session unavailable")


async def get_tenant_session(context: TenantContext = Depends(get_tenant_context)) -> AsyncIterator[AsyncSession]:
    async for session in tenant_session(context):
        yield session
