import asyncio
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.secrets import secret_resolver
from app.core.tenant_context import TenantContext

platform_engine = create_async_engine(settings.platform_database_url, pool_pre_ping=True, future=True)
PlatformSession = async_sessionmaker(platform_engine, expire_on_commit=False, class_=AsyncSession)


@dataclass(slots=True)
class _TenantEngineEntry:
    engine: AsyncEngine
    last_used: float


_tenant_engines: OrderedDict[str, _TenantEngineEntry] = OrderedDict()
_tenant_engines_lock = asyncio.Lock()
_tenant_engine_metrics = {"hits": 0, "misses": 0, "evictions": 0}


async def platform_session() -> AsyncIterator[AsyncSession]:
    async with PlatformSession() as session:
        yield session


def _tenant_cache_key(context: TenantContext) -> str:
    return ":".join(
        [
            settings.postgres_host,
            str(settings.postgres_port),
            context.database,
            context.database_user,
            str(context.database_credential_version),
        ]
    )


async def _purge_expired_engines(now: float) -> None:
    ttl = max(settings.tenant_engine_cache_ttl_seconds, 1)
    expired = [
        key for key, entry in _tenant_engines.items()
        if now - entry.last_used >= ttl
    ]
    for key in expired:
        entry = _tenant_engines.pop(key)
        await entry.engine.dispose()
        _tenant_engine_metrics["evictions"] += 1


async def get_tenant_engine(context: TenantContext) -> AsyncEngine:
    cache_key = _tenant_cache_key(context)
    now = time.monotonic()
    async with _tenant_engines_lock:
        await _purge_expired_engines(now)
        entry = _tenant_engines.get(cache_key)
        if entry is not None:
            entry.last_used = now
            _tenant_engines.move_to_end(cache_key)
            _tenant_engine_metrics["hits"] += 1
            return entry.engine

        password = secret_resolver.resolve(context.database_password_ref)
        engine = create_async_engine(
            settings.tenant_database_url(context.database, context.database_user, password),
            pool_pre_ping=True,
            future=True,
        )
        _tenant_engines[cache_key] = _TenantEngineEntry(engine=engine, last_used=now)
        _tenant_engine_metrics["misses"] += 1

        max_entries = max(settings.tenant_engine_cache_max, 1)
        while len(_tenant_engines) > max_entries:
            _, evicted = _tenant_engines.popitem(last=False)
            await evicted.engine.dispose()
            _tenant_engine_metrics["evictions"] += 1
        return engine


async def invalidate_tenant_engine(context: TenantContext) -> None:
    cache_key = _tenant_cache_key(context)
    async with _tenant_engines_lock:
        entry = _tenant_engines.pop(cache_key, None)
        if entry is not None:
            await entry.engine.dispose()
            _tenant_engine_metrics["evictions"] += 1


async def close_database_engines() -> None:
    async with _tenant_engines_lock:
        entries = list(_tenant_engines.values())
        _tenant_engines.clear()
    for entry in entries:
        await entry.engine.dispose()
    await platform_engine.dispose()


def tenant_engine_cache_metrics() -> dict[str, int]:
    return {**_tenant_engine_metrics, "size": len(_tenant_engines)}


async def tenant_session(context: TenantContext) -> AsyncIterator[AsyncSession]:
    engine = await get_tenant_engine(context)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
