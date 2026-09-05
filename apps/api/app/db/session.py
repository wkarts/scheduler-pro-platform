import asyncio
import os
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.secrets import secret_resolver
from app.core.tenant_context import TenantContext
from app.db.engine_registry import BoundedEngineRegistry


def database_connect_args(scope: str) -> dict[str, Any]:
    server_settings = {
        "application_name": f"{settings.db_service_name}:{scope}"[:63],
    }
    for name, value in (
        ("statement_timeout", settings.db_statement_timeout_ms),
        ("lock_timeout", settings.db_lock_timeout_ms),
        ("idle_in_transaction_session_timeout", settings.db_idle_transaction_timeout_ms),
    ):
        if value:
            server_settings[name] = str(value)
    return {"timeout": settings.db_connect_timeout_seconds, "server_settings": server_settings}


def _engine_options(*, tenant: bool) -> dict[str, Any]:
    return {
        "pool_size": settings.db_tenant_pool_size if tenant else settings.db_platform_pool_size,
        "max_overflow": (
            settings.db_tenant_max_overflow if tenant else settings.db_platform_max_overflow
        ),
        "pool_timeout": settings.db_pool_timeout_seconds,
        "pool_recycle": settings.db_pool_recycle_seconds,
        "pool_pre_ping": True,
        "pool_use_lifo": True,
        "connect_args": database_connect_args("tenant" if tenant else "platform"),
    }


platform_engine = create_async_engine(settings.platform_database_url, **_engine_options(tenant=False))
PlatformSession = async_sessionmaker(platform_engine, expire_on_commit=False, class_=AsyncSession)


def _new_registry() -> BoundedEngineRegistry[AsyncEngine]:
    return BoundedEngineRegistry(
        maximum=settings.tenant_engine_cache_max,
        ttl=settings.tenant_engine_cache_ttl_seconds,
        wait_timeout=settings.db_pool_timeout_seconds,
        is_busy=lambda engine: bool(getattr(engine.pool, "checkedout", lambda: 0)()),
    )


_tenant_registry = _new_registry()


async def platform_session() -> AsyncGenerator[AsyncSession, None]:
    async with PlatformSession() as session:
        yield session


def _tenant_cache_key(context: TenantContext) -> str:
    # Aliases/custom domains of ONE tenant must not create duplicate pools.
    # Keep tenant identity + credential reference/version to preserve isolation.
    return repr((
        context.tenant_id, settings.postgres_host, settings.postgres_port,
        context.database, context.database_user, context.database_password_ref,
        context.database_credential_version,
    ))


def _create_tenant_engine(context: TenantContext) -> AsyncEngine:
    password = secret_resolver.resolve(context.database_password_ref)
    return create_async_engine(
        settings.tenant_database_url(context.database, context.database_user, password),
        **_engine_options(tenant=True),
    )


async def get_tenant_engine(context: TenantContext) -> AsyncEngine:
    # Retained for compatibility. Runtime callers use tenant_session/tenant_engine_lease.
    return await _tenant_registry.get(_tenant_cache_key(context), lambda: _create_tenant_engine(context))


@asynccontextmanager
async def tenant_engine_lease(context: TenantContext) -> AsyncIterator[AsyncEngine]:
    async with _tenant_registry.lease(
        _tenant_cache_key(context), lambda: _create_tenant_engine(context),
    ) as engine:
        yield engine


async def invalidate_tenant_engine(context: TenantContext) -> None:
    await _tenant_registry.invalidate(_tenant_cache_key(context))


async def close_database_engines() -> None:
    await _tenant_registry.close()
    await platform_engine.dispose()


def reset_database_engines_after_fork() -> None:
    """Detach inherited pools WITHOUT closing the parent's connections."""
    global _tenant_registry
    platform_engine.sync_engine.dispose(close=False)
    for entry in _tenant_registry.entries.values():
        entry.engine.sync_engine.dispose(close=False)
    _tenant_registry = _new_registry()


async def reap_idle_tenant_engines() -> None:
    while True:
        await asyncio.sleep(min(settings.tenant_engine_cache_ttl_seconds, 30))
        await _tenant_registry.prune()


def tenant_engine_cache_metrics() -> dict[str, int]:
    return _tenant_registry.metrics()


def database_pool_metrics() -> dict[str, Any]:
    pool = platform_engine.pool
    return {
        "service": settings.db_service_name,
        "pid": os.getpid(),
        "platform": {
            "size": getattr(pool, "size", lambda: 0)(),
            "checked_out": getattr(pool, "checkedout", lambda: 0)(),
            "overflow": max(0, getattr(pool, "overflow", lambda: 0)()),
        },
        "tenant_cache": tenant_engine_cache_metrics(),
        "maximum_connections_per_process": (
            settings.db_platform_pool_size + settings.db_platform_max_overflow
            + settings.tenant_engine_cache_max
            * (settings.db_tenant_pool_size + settings.db_tenant_max_overflow)
        ),
    }


async def tenant_session(context: TenantContext) -> AsyncGenerator[AsyncSession, None]:
    async with tenant_engine_lease(context) as engine:
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            session.info["tenant_id"] = context.tenant_id
            session.info["tenant_slug"] = context.slug
            session.info["tenant_hostname"] = context.hostname
            session.info["tenant_timezone"] = context.timezone
            yield session
