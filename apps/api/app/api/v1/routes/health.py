import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

import aio_pika
import asyncpg
import boto3
import redis.asyncio as redis
import structlog
from botocore.config import Config as BotoConfig
from fastapi import APIRouter, Request
from fastapi.responses import ORJSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import resolve_request_hostname
from app.core.config import settings
from app.core.responses import success
from app.db.session import PlatformSession, tenant_engine_lease, database_connect_args
from app.db.connection_budget import CAPACITY_SQL, capacity_snapshot
from app.services.tenant_resolver import TenantResolver

router = APIRouter()
PLATFORM_MIGRATION_HEAD = "platform_0013_integrations"
TENANT_MIGRATION_HEAD = "tenant_0013_integrations"
APP_VERSION = os.getenv("APP_VERSION", "2.0.1")
APP_RELEASE_TAG = os.getenv("APP_RELEASE_TAG", "").strip()
APP_BUILD_SHA = os.getenv("APP_BUILD_SHA", "").strip()


@router.get("/health")
async def health() -> dict[str, Any]:
    return success({"status": "ok", "service": "scheduler-pro-api", "version": APP_VERSION})


@router.get("/health/live")
async def live() -> dict[str, Any]:
    return success({"live": True, "version": APP_VERSION})


@router.get("/version")
async def version() -> dict[str, Any]:
    return success(
        {
            "name": "Scheduler Pro",
            "version": APP_VERSION,
            "release_tag": APP_RELEASE_TAG or None,
            "build_sha": APP_BUILD_SHA or None,
            "tenant_schema": TENANT_MIGRATION_HEAD,
            "platform_schema": PLATFORM_MIGRATION_HEAD,
        }
    )


async def _check_platform() -> tuple[str, str | None]:
    # SELECT 1 on a warm platform pool can succeed while new tenant logins fail.
    connection = await asyncpg.connect(
        host=settings.postgres_host, port=settings.postgres_port,
        user=settings.postgres_user, password=settings.postgres_password,
        database=settings.postgres_db, **database_connect_args("readiness"),
    )
    try:
        revision = await connection.fetchval("select version_num from alembic_version")
        if revision != PLATFORM_MIGRATION_HEAD:
            return "failed", f"migration:{revision or 'missing'}"
        row = await connection.fetchrow(CAPACITY_SQL)
        snapshot = capacity_snapshot(
            row, warning=settings.db_capacity_warning_percent,
            critical=settings.db_capacity_critical_percent,
        )
        if snapshot["status"] != "ok":
            structlog.get_logger("scheduler.database").warning(
                "database_connection_pressure", **snapshot,
            )
        if snapshot["status"] == "critical":
            return "failed", "connection_capacity"
        return "ok", "connection_pressure" if snapshot["status"] == "warning" else None
    finally:
        await connection.close(timeout=1)


async def _check_redis() -> tuple[str, str | None]:
    client = redis.from_url(  # type: ignore[no-untyped-call]
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        if not await client.ping():
            return "failed", "ping"
        return "ok", None
    finally:
        await client.aclose()


async def _check_rabbitmq() -> tuple[str, str | None]:
    connection = await aio_pika.connect(settings.rabbitmq_url, timeout=2)
    await connection.close()
    return "ok", None


def _s3_list_buckets() -> None:
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(connect_timeout=2, read_timeout=2, retries={"max_attempts": 1}),
    )
    try:
        client.list_buckets()
    finally:
        client.close()


async def _check_s3() -> tuple[str, str | None]:
    await asyncio.to_thread(_s3_list_buckets)
    return "ok", None


def resolve_request_hostname_from_value(value: str) -> str:
    from app.api.deps import normalize_hostname

    return normalize_hostname(value)


def _tenant_probe_required(hostname: str) -> bool:
    if settings.app_env == "development":
        return True
    platform_hostname = resolve_request_hostname_from_value(settings.public_platform_domain)
    admin_hostnames = {
        resolve_request_hostname_from_value(value) for value in settings.admin_platform_domains
    }
    return hostname not in {platform_hostname, "localhost", "127.0.0.1", "::1", *admin_hostnames}


async def _check_tenant(request: Request) -> tuple[str, str | None]:
    hostname = resolve_request_hostname(request)
    if not _tenant_probe_required(hostname):
        return "not_applicable", None
    async with PlatformSession() as platform:
        context = await TenantResolver(platform).resolve(hostname)
    async with tenant_engine_lease(context) as engine:
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as session:
            revision = (
                await session.execute(text("select version_num from alembic_version"))
            ).scalar_one_or_none()
            if revision != TENANT_MIGRATION_HEAD:
                return "failed", f"migration:{revision or 'missing'}"
            await session.execute(text("select 1"))
    return "ok", None


_shared_checks: dict[str, dict[str, str]] | None = None
_shared_checked_at = 0.0
_shared_task: asyncio.Task[dict[str, dict[str, str]]] | None = None


async def _bounded_probe(probe: Callable[[], Awaitable[tuple[str, str | None]]]) -> dict[str, str]:
    try:
        state, detail = await asyncio.wait_for(probe(), settings.health_probe_timeout_seconds)
    except Exception:
        state, detail = "failed", "unavailable"
    result = {"status": state}
    if detail:
        result["detail"] = detail
    return result


async def _collect_shared_checks() -> dict[str, dict[str, str]]:
    global _shared_checks, _shared_checked_at
    probes = {
        "postgres_platform": _check_platform,
        "redis": _check_redis,
        "rabbitmq": _check_rabbitmq,
        "storage": _check_s3,
    }
    results = await asyncio.gather(*(_bounded_probe(p) for p in probes.values()))
    _shared_checks = dict(zip(probes, results, strict=True))
    _shared_checked_at = time.monotonic()
    return _shared_checks


async def _shared_dependency_checks() -> dict[str, dict[str, str]]:
    global _shared_task
    if _shared_checks is not None and time.monotonic() - _shared_checked_at < settings.health_cache_seconds:
        return dict(_shared_checks)
    if _shared_task is None or _shared_task.done():
        _shared_task = asyncio.create_task(_collect_shared_checks())
    # Disconnecting a monitor must not cancel the one probe shared by other clients.
    return dict(await asyncio.shield(_shared_task))


async def close_readiness_tasks() -> None:
    global _shared_task, _shared_checks, _shared_checked_at
    if _shared_task is not None:
        _shared_task.cancel()
        await asyncio.gather(_shared_task, return_exceptions=True)
    _shared_task = None
    _shared_checks = None
    _shared_checked_at = 0.0


@router.get("/health/ready")
async def ready(request: Request) -> ORJSONResponse:
    checks = await _shared_dependency_checks()
    if checks["postgres_platform"]["status"] == "ok":
        checks["tenant"] = await _bounded_probe(lambda: _check_tenant(request))
    else:
        checks["tenant"] = {"status": "failed", "detail": "database_unavailable"}
    ready_state = all(v["status"] in {"ok", "not_applicable"} for v in checks.values())
    return ORJSONResponse(
        status_code=200 if ready_state else 503,
        headers={"Cache-Control": "no-store"},
        content=success({"ready": ready_state, "checks": checks}),
    )
