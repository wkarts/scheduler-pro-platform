from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.tenant_context import TenantContext

platform_engine = create_async_engine(settings.platform_database_url, pool_pre_ping=True, future=True)
PlatformSession = async_sessionmaker(platform_engine, expire_on_commit=False, class_=AsyncSession)
_tenant_engines: dict[str, AsyncEngine] = {}


async def platform_session() -> AsyncIterator[AsyncSession]:
    async with PlatformSession() as session:
        yield session


def get_tenant_engine(context: TenantContext) -> AsyncEngine:
    cache_key = context.database
    if cache_key not in _tenant_engines:
        url = settings.tenant_database_url(context.database, context.database_user, context.database_password_ref)
        _tenant_engines[cache_key] = create_async_engine(url, pool_pre_ping=True, future=True)
    return _tenant_engines[cache_key]


async def tenant_session(context: TenantContext) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(get_tenant_engine(context), expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
