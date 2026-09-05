"""Regression coverage for the closeable session contracts used by aclosing."""
import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing, asynccontextmanager
from types import SimpleNamespace
from typing import Any, get_type_hints

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import TenantContext
from app.db import session as database


@pytest.mark.parametrize("provider", [database.platform_session, database.tenant_session])
def test_session_annotation_exposes_aclose(provider: Any) -> None:
    assert get_type_hints(provider)["return"] == AsyncGenerator[AsyncSession, None]


@pytest.mark.parametrize("scope", ["platform", "tenant"])
@pytest.mark.parametrize("exit_kind", ["exhausted", "break", "return", "error", "cancel"])
@pytest.mark.asyncio
async def test_session_and_lease_close_on_every_consumer_exit(
    monkeypatch: Any, scope: str, exit_kind: str,
) -> None:
    events: list[str] = []
    acquired = asyncio.Event()
    pending = asyncio.Event()
    fake_session = SimpleNamespace(info={})
    context = TenantContext(
        tenant_id="tenant-a", slug="a", database="tenant_a",
        database_user="tenant_a_user", database_password_ref="secret://env/TEST_PASSWORD",
        storage_bucket="tenant-a", hostname="a.example.invalid",
    )

    @asynccontextmanager
    async def managed_session() -> AsyncIterator[Any]:
        events.append("session_open")
        try:
            yield fake_session
        finally:
            events.append("session_close")

    @asynccontextmanager
    async def managed_engine(_: TenantContext) -> AsyncIterator[object]:
        events.append("engine_lease_open")
        try:
            yield object()
        finally:
            events.append("engine_lease_close")

    monkeypatch.setattr(database, "PlatformSession", managed_session)
    monkeypatch.setattr(database, "tenant_engine_lease", managed_engine)
    monkeypatch.setattr(database, "async_sessionmaker", lambda *args, **kwargs: managed_session)

    async def consume() -> None:
        generator = (
            database.platform_session() if scope == "platform" else database.tenant_session(context)
        )
        async with aclosing(generator) as sessions:
            async for current in sessions:
                assert current is fake_session
                if scope == "tenant":
                    assert current.info["tenant_id"] == context.tenant_id
                    assert current.info["tenant_hostname"] == context.hostname
                acquired.set()
                if exit_kind == "break":
                    break
                if exit_kind == "return":
                    return
                if exit_kind == "error":
                    raise RuntimeError("consumer failure")
                if exit_kind == "cancel":
                    await pending.wait()

    if exit_kind == "cancel":
        task = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(acquired.wait(), timeout=1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    elif exit_kind == "error":
        with pytest.raises(RuntimeError, match="consumer failure"):
            await consume()
    else:
        await consume()

    expected = ["session_open", "session_close"]
    if scope == "tenant":
        expected = ["engine_lease_open", *expected, "engine_lease_close"]
    assert events == expected
