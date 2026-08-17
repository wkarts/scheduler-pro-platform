import httpx
import pytest

from app import log_agent
from app import platform_bootstrap
from app.core.config import settings


class _MappingsResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _ExecuteResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return _MappingsResult(self._row)


class _FakeSession:
    def __init__(self, row):
        self.row = row
        self.execute_calls = 0
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, statement, params):
        self.execute_calls += 1
        return _ExecuteResult(self.row)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_log_agent_health_stays_alive_when_docker_socket_is_unavailable(monkeypatch) -> None:
    async def unavailable():
        raise httpx.ConnectError("permission denied")

    monkeypatch.setattr(log_agent, "_project_containers", unavailable)

    payload = await log_agent.health(x_log_agent_token=log_agent._token())

    assert payload["ok"] is True
    assert payload["docker"]["ok"] is False
    assert payload["docker"]["status"] == "degraded"


@pytest.mark.asyncio
async def test_existing_superadmin_is_preserved_when_env_has_legacy_short_password(monkeypatch) -> None:
    session = _FakeSession(
        {"email": "admin@scheduler.argws.com.br", "is_super_admin": True, "is_active": True}
    )
    monkeypatch.setattr(platform_bootstrap, "PlatformSession", lambda: session)
    monkeypatch.setattr(settings, "platform_admin_email", "admin@scheduler.argws.com.br")
    monkeypatch.setattr(settings, "platform_admin_password", "legacy")

    await platform_bootstrap.bootstrap_platform_admin()

    assert session.execute_calls == 1
    assert session.committed is False


@pytest.mark.asyncio
async def test_new_installation_still_rejects_short_platform_admin_password(monkeypatch) -> None:
    session = _FakeSession(None)
    monkeypatch.setattr(platform_bootstrap, "PlatformSession", lambda: session)
    monkeypatch.setattr(settings, "platform_admin_email", "admin@scheduler.argws.com.br")
    monkeypatch.setattr(settings, "platform_admin_password", "legacy")

    with pytest.raises(RuntimeError, match="at least 12 characters"):
        await platform_bootstrap.bootstrap_platform_admin()
