from typing import Any

import asyncpg
import pytest

from app.core.config import settings
from app.db import postgres_admin
from app.services import tenant_lifecycle_service
from app.services.tenant_lifecycle_service import TenantLifecycleService


class FakeAdminConnection:
    def __init__(self, *, privileged: bool) -> None:
        self.privileged = privileged
        self.closed = False
        self.statements: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, _query: str) -> dict[str, bool]:
        return {
            "rolsuper": self.privileged,
            "rolcreaterole": False,
            "rolcreatedb": False,
        }

    async def execute(self, query: str, *args: Any) -> str:
        self.statements.append((query, args))
        return "OK"

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_admin_connection_falls_back_when_postgres_password_is_wrong(monkeypatch) -> None:
    monkeypatch.setattr(settings, "postgres_admin_user", "postgres")
    monkeypatch.setattr(settings, "postgres_admin_password", "wrong-admin-password")
    monkeypatch.setattr(settings, "postgres_user", "scheduler")
    monkeypatch.setattr(settings, "postgres_password", "platform-password")

    platform_conn = FakeAdminConnection(privileged=True)
    attempted_users: list[str] = []

    async def fake_connect(**kwargs: Any) -> Any:
        user = str(kwargs["user"])
        attempted_users.append(user)
        if user == "postgres":
            raise asyncpg.InvalidPasswordError("password authentication failed")
        return platform_conn

    monkeypatch.setattr(postgres_admin.asyncpg, "connect", fake_connect)

    conn = await postgres_admin.connect_postgres_admin()

    assert conn is platform_conn
    assert attempted_users == ["postgres", "scheduler"]
    assert platform_conn.closed is False


@pytest.mark.asyncio
async def test_admin_connection_skips_authenticated_user_without_create_privileges(monkeypatch) -> None:
    monkeypatch.setattr(settings, "postgres_admin_user", "postgres")
    monkeypatch.setattr(settings, "postgres_admin_password", "admin-password")
    monkeypatch.setattr(settings, "postgres_user", "scheduler")
    monkeypatch.setattr(settings, "postgres_password", "platform-password")

    limited_conn = FakeAdminConnection(privileged=False)
    platform_conn = FakeAdminConnection(privileged=True)

    async def fake_connect(**kwargs: Any) -> Any:
        if kwargs["user"] == "postgres":
            return limited_conn
        return platform_conn

    monkeypatch.setattr(postgres_admin.asyncpg, "connect", fake_connect)

    conn = await postgres_admin.connect_postgres_admin()

    assert conn is platform_conn
    assert limited_conn.closed is True
    assert platform_conn.closed is False


@pytest.mark.asyncio
async def test_tenant_purge_uses_same_resilient_postgres_admin_connection(monkeypatch) -> None:
    fake_conn = FakeAdminConnection(privileged=True)

    async def fake_admin_connect(database: str | None = None) -> Any:
        assert database is None
        return fake_conn

    monkeypatch.setattr(tenant_lifecycle_service, "connect_postgres_admin", fake_admin_connect)

    service = TenantLifecycleService.__new__(TenantLifecycleService)
    await service._drop_database("tenant_1d5955e6", "tenant_1d5955e6_user")

    sql = "\n".join(statement for statement, _ in fake_conn.statements)
    assert "pg_terminate_backend" in sql
    assert 'drop database if exists "tenant_1d5955e6"' in sql
    assert 'drop role if exists "tenant_1d5955e6_user"' in sql
    assert fake_conn.closed is True
