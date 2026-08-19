from uuid import uuid4

import asyncpg
import httpx
import pytest

from app.core.config import settings

pytestmark = pytest.mark.integration


async def test_tenant_browser_telemetry_is_persistent_and_visible_to_control_plane(
    client: httpx.AsyncClient,
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.dev_tenant_admin_email,
            "password": settings.dev_tenant_admin_password,
        },
    )
    assert login.status_code == 200, login.text
    tenant_token = login.json()["data"]["access_token"]

    marker = f"agenda-freeze-probe-{uuid4().hex}"
    telemetry = await client.post(
        "/api/v1/telemetry/events",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={
            "level": "WARNING",
            "event": marker,
            "message": "Teste integrado de telemetria do WebApp.",
            "details": {
                "tab": "Agendar",
                "password": "must-not-be-stored",
                "safe": "visible",
            },
        },
    )
    assert telemetry.status_code == 200, telemetry.text

    platform = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    try:
        tenant_id = await platform.fetchval(
            "select id::text from tenants where slug=$1",
            settings.dev_tenant_slug,
        )
        platform_row = await platform.fetchrow(
            """
            select event, details
            from platform_log_entries
            where tenant_id=$1::uuid and event=$2
            order by created_at desc limit 1
            """,
            tenant_id,
            marker,
        )
        assert platform_row is not None
        assert platform_row["details"]["password"] == "[redacted]"
        assert platform_row["details"]["safe"] == "visible"
    finally:
        await platform.close()

    tenant = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.dev_tenant_database_user,
        password=settings.dev_tenant_database_password,
        database=settings.dev_tenant_database,
    )
    try:
        tenant_row = await tenant.fetchrow(
            "select event, details from tenant_log_entries where event=$1 order by created_at desc limit 1",
            marker,
        )
        assert tenant_row is not None
        assert tenant_row["details"]["password"] == "[redacted]"
    finally:
        await tenant.close()

    admin_login = await client.post(
        "/api/v1/auth/platform/login",
        json={
            "email": settings.dev_platform_admin_email,
            "password": settings.dev_platform_admin_password,
        },
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["data"]["access_token"]
    diagnostics = await client.get(
        f"/api/v1/platform/tenant-management/{tenant_id}/logs",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"search": marker, "limit": 50},
    )
    assert diagnostics.status_code == 200, diagnostics.text
    rows = diagnostics.json()["data"]
    assert any(row["event"] == marker for row in rows)
    assert {row.get("scope") for row in rows if row["event"] == marker} >= {"platform", "tenant"}
