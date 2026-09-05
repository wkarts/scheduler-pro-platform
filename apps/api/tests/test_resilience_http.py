"""API-boundary regression tests. Requires the project's normal Python dependencies."""
from typing import Any

import asyncpg
import pytest
from starlette.requests import Request

from app.api import deps
from app.api.v1.routes import health, realtime
from app.core.config import settings
from app.core.errors import unhandled_error_handler
from app.core.tenant_context import TenantContext
from app.db.session import _tenant_cache_key
from app.workers import agenda_report_tasks, tasks


def request() -> Request:
    return Request({'type':'http','method':'GET','path':'/api/v1/health/ready',
                    'headers':[(b'host',b'localhost')],'query_string':b'',
                    'server':('localhost',80),'client':('127.0.0.1',1234),
                    'scheme':'http','app':type('App',(),{'debug':False})()})


def context(hostname: str = 'a.example.invalid', credential_version: int = 1) -> TenantContext:
    return TenantContext(tenant_id='tenant-a',slug='a',database='tenant_a',database_user='tenant_a_user',
                         database_password_ref='secret://env/TEST_PASSWORD',storage_bucket='tenant-a',
                         hostname=hostname,database_credential_version=credential_version)


def test_aliases_share_credentials_not_pools_by_hostname() -> None:
    assert _tenant_cache_key(context()) == _tenant_cache_key(context('alias.example.invalid'))
    assert _tenant_cache_key(context()) != _tenant_cache_key(context(credential_version=2))


def test_reports_share_the_worker_runtime() -> None:
    assert agenda_report_tasks._run is tasks._run


@pytest.mark.asyncio
async def test_tenant_resolution_closes_platform_generator_before_return(monkeypatch: Any) -> None:
    closed=[]
    async def session() -> Any:
        try:
            yield object()
        finally:
            closed.append(True)
    class Resolver:
        def __init__(self, _: Any) -> None:
            pass
        async def resolve(self, _: str) -> TenantContext:
            return context()
    monkeypatch.setattr(deps,'platform_session',session)
    monkeypatch.setattr(deps,'TenantResolver',Resolver)
    result=await deps.get_tenant_context(request())
    assert result.tenant_id=='tenant-a'
    assert closed==[True]


@pytest.mark.asyncio
async def test_connection_exhaustion_has_503_not_invalid_credentials() -> None:
    response=await unhandled_error_handler(request(),asyncpg.TooManyConnectionsError())
    assert response.status_code==503
    assert response.headers['retry-after']=='5'
    assert b'DATABASE_TEMPORARILY_UNAVAILABLE' in response.body


@pytest.mark.asyncio
async def test_readiness_fails_when_new_postgres_connection_is_rejected(monkeypatch: Any) -> None:
    await health.close_readiness_tasks()
    async def reject(**_: Any) -> Any:
        raise asyncpg.TooManyConnectionsError()
    async def ok() -> tuple[str,None]:
        return 'ok',None
    async def tenant(_: Any) -> Any:
        pytest.fail('Do not pressure tenant databases when platform connectivity is already failing')
    monkeypatch.setattr(health.asyncpg,'connect',reject)
    for name in ('_check_redis','_check_rabbitmq','_check_s3'):
        monkeypatch.setattr(health,name,ok)
    monkeypatch.setattr(health,'_check_tenant',tenant)
    try:
        result=await health.ready(request())
        assert result.status_code==503
        assert b'postgres_platform' in result.body
    finally:
        await health.close_readiness_tasks()


@pytest.mark.asyncio
async def test_readiness_probe_uses_fresh_connection_and_checks_headroom(monkeypatch: Any) -> None:
    calls=[]
    class Connection:
        async def fetchval(self, _: str) -> str:
            return health.PLATFORM_MIGRATION_HEAD
        async def fetchrow(self, _: str) -> dict[str,int]:
            return {'maximum':100,'superuser_reserved':3,'reserved':0,'used':97,
                    'active':7,'idle':90,'idle_in_transaction':0}
        async def close(self, **_: Any) -> None:
            calls.append('close')
    async def connect(**kwargs: Any) -> Connection:
        assert kwargs['timeout']>0
        calls.append('connect')
        return Connection()
    monkeypatch.setattr(health.asyncpg,'connect',connect)
    assert await health._check_platform()==('failed','connection_capacity')
    assert await health._check_platform()==('failed','connection_capacity')
    assert calls==['connect','close','connect','close']


@pytest.mark.asyncio
async def test_probe_deadline_bounds_a_hanging_dependency(monkeypatch: Any) -> None:
    import asyncio
    monkeypatch.setattr(settings,'health_probe_timeout_seconds',0.01)
    async def hang() -> tuple[str,None]:
        await asyncio.sleep(10)
        return 'ok',None
    result=await health._bounded_probe(hang)
    assert result['status']=='failed'


@pytest.mark.asyncio
async def test_sse_releases_its_session_before_yielding_data(monkeypatch: Any) -> None:
    closed=[]
    class Session:
        async def rollback(self) -> None:
            pass
    async def session(_: Any) -> Any:
        try:
            yield Session()
        finally:
            closed.append(True)
    class Service:
        def __init__(self, _: Any) -> None:
            pass
        async def list_after(self, *args: Any, **kwargs: Any) -> list[Any]:
            return []
    class StreamRequest:
        async def is_disconnected(self) -> bool:
            return False
    monkeypatch.setattr(realtime,'tenant_session',session)
    monkeypatch.setattr(realtime,'RealtimeEventService',Service)
    response=await realtime.event_stream(StreamRequest(),after=0,context=context())
    iterator=response.body_iterator
    assert await anext(iterator)==': keepalive\n\n'
    assert closed==[True]
    await iterator.aclose()
