import asyncio
from typing import Any

import aio_pika
import boto3
import redis.asyncio as redis
from botocore.config import Config as BotoConfig
from fastapi import APIRouter, Request
from fastapi.responses import ORJSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import resolve_request_hostname
from app.core.config import settings
from app.core.responses import success
from app.db.session import PlatformSession, get_tenant_engine
from app.services.tenant_resolver import TenantResolver

router = APIRouter()

PLATFORM_MIGRATION_HEAD = "platform_0004"
TENANT_MIGRATION_HEAD = "tenant_0003_scheduler_engine"


@router.get("/health")
async def health() -> dict[str, Any]:
    return success({"status": "ok", "service": "scheduler-pro-api"})


@router.get("/health/live")
async def live() -> dict[str, Any]:
    return success({"live": True})


async def _check_platform() -> tuple[str, str | None]:
    async with PlatformSession() as session:
        await session.execute(text("select 1"))
        revision = (await session.execute(text("select version_num from alembic_version"))).scalar_one_or_none()
        if revision != PLATFORM_MIGRATION_HEAD:
            return "failed", f"migration:{revision or 'missing'}"
    return "ok", None


async def _check_redis() -> tuple[str, str | None]:
    client = redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)  # type: ignore[no-untyped-call]
    try:
        if not await client.ping():
            return "failed", "ping"
        return "ok", None
    finally:
        await client.aclose()


async def _check_rabbitmq() -> tuple[str, str | None]:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url, timeout=2)
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
    client.list_buckets()


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
    return hostname not in {platform_hostname, "localhost", "127.0.0.1", "::1"}


async def _check_tenant(request: Request) -> tuple[str, str | None]:
    hostname = resolve_request_hostname(request)
    if not _tenant_probe_required(hostname):
        return "not_applicable", None
    async with PlatformSession() as platform:
        context = await TenantResolver(platform).resolve(hostname)
    engine = await get_tenant_engine(context)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        revision = (await session.execute(text("select version_num from alembic_version"))).scalar_one_or_none()
        if revision != TENANT_MIGRATION_HEAD:
            return "failed", f"migration:{revision or 'missing'}"
        await session.execute(text("select 1"))
    return "ok", None


@router.get("/health/ready")
async def ready(request: Request) -> ORJSONResponse:
    checks: dict[str, dict[str, str]] = {}
    probes = {"postgres_platform": _check_platform, "redis": _check_redis, "rabbitmq": _check_rabbitmq, "storage": _check_s3}
    ready_state = True
    for name, probe in probes.items():
        try:
            state, detail = await probe()
        except Exception:
            state, detail = "failed", "unavailable"
        checks[name] = {"status": state}
        if detail:
            checks[name]["detail"] = detail
        ready_state = ready_state and state in {"ok", "not_applicable"}
    try:
        state, detail = await _check_tenant(request)
    except Exception:
        state, detail = "failed", "unavailable"
    checks["tenant"] = {"status": state}
    if detail:
        checks["tenant"]["detail"] = detail
    ready_state = ready_state and state in {"ok", "not_applicable"}
    return ORJSONResponse(status_code=200 if ready_state else 503, content=success({"ready": ready_state, "checks": checks}))
