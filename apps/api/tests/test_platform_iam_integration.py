import time
from uuid import uuid4

import asyncpg
import httpx
import pytest

from app.core.config import settings
from app.core.secrets import secret_resolver
from app.services.two_factor_service import TwoFactorService

pytestmark = pytest.mark.integration


async def _platform_secret(email: str) -> str:
    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    try:
        reference = await conn.fetchval(
            "select two_factor_secret_ref from platform_users where lower(email)=lower($1)",
            email,
        )
    finally:
        await conn.close()
    assert reference
    return secret_resolver.resolve(str(reference))


async def platform_login(
    client: httpx.AsyncClient,
    email: str | None = None,
    password: str | None = None,
) -> dict:
    login_email = email or settings.dev_platform_admin_email
    response = await client.post(
        "/api/v1/auth/platform/login",
        json={
            "email": login_email,
            "password": password or settings.dev_platform_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    headers = {"authorization": f"Bearer {data['access_token']}"}

    state_response = await client.get(
        "/api/v1/auth/platform/2fa/state",
        headers=headers,
    )
    assert state_response.status_code == 200, state_response.text
    state = state_response.json()["data"]

    if state["enabled"]:
        secret = await _platform_secret(login_email)
        code = TwoFactorService.code_at(secret, int(time.time()))
        verified = await client.post(
            "/api/v1/auth/platform/2fa/verify",
            headers=headers,
            json={"code": code},
        )
        assert verified.status_code == 200, verified.text
    else:
        setup = await client.post(
            "/api/v1/auth/platform/2fa/setup",
            headers=headers,
            json={},
        )
        assert setup.status_code == 200, setup.text
        secret = setup.json()["data"]["manual_key"]
        code = TwoFactorService.code_at(secret, int(time.time()))
        confirmed = await client.post(
            "/api/v1/auth/platform/2fa/confirm",
            headers=headers,
            json={"code": code},
        )
        assert confirmed.status_code == 200, confirmed.text

    return data


async def test_platform_admin_role_permissions_and_tenant_scope(
    client: httpx.AsyncClient,
) -> None:
    super_login = await platform_login(client)
    super_headers = {"authorization": f"Bearer {super_login['access_token']}"}

    tenant_response = await client.get("/api/v1/platform/tenants", headers=super_headers)
    assert tenant_response.status_code == 200, tenant_response.text
    tenant_rows = tenant_response.json()["data"]
    scoped_tenant = next(row for row in tenant_rows if row["slug"] == settings.dev_tenant_slug)

    platform = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    outside_slug = f"iam-outside-{uuid4().hex[:8]}"
    outside_id = await platform.fetchval(
        """
        insert into tenants(name, slug, status, timezone, settings)
        values('IAM Outside', $1, 'ACTIVE', 'America/Bahia', '{}')
        returning id::text
        """,
        outside_slug,
    )

    role_name = f"Scoped Support {uuid4().hex[:8]}"
    role_response = await client.post(
        "/api/v1/platform/access/roles",
        headers=super_headers,
        json={
            "name": role_name,
            "description": "Integration scoped admin",
            "permissions": [
                "platform.dashboard.read",
                "tenants.read",
                "domains.read",
                "observability.read",
            ],
        },
    )
    assert role_response.status_code == 200, role_response.text
    role = role_response.json()["data"]

    user_email = f"scoped-{uuid4().hex}@platform.example"
    user_password = "Scoped-Platform-Password-2026!"
    user_response = await client.post(
        "/api/v1/platform/access/users",
        headers=super_headers,
        json={
            "email": user_email,
            "display_name": "Scoped Admin",
            "password": user_password,
            "role_ids": [role["id"]],
            "tenant_ids": [scoped_tenant["id"]],
        },
    )
    assert user_response.status_code == 200, user_response.text
    user = user_response.json()["data"]

    try:
        scoped_login = await platform_login(client, user_email, user_password)
        scoped_headers = {"authorization": f"Bearer {scoped_login['access_token']}"}

        scoped_tenants_response = await client.get(
            "/api/v1/platform/tenants",
            headers=scoped_headers,
        )
        assert scoped_tenants_response.status_code == 200, scoped_tenants_response.text
        visible = scoped_tenants_response.json()["data"]
        visible_ids = {row["id"] for row in visible}
        assert scoped_tenant["id"] in visible_ids
        assert outside_id not in visible_ids

        dashboard = await client.get(
            "/api/v1/platform/dashboard",
            headers=scoped_headers,
        )
        assert dashboard.status_code == 200, dashboard.text
        assert dashboard.json()["data"]["totals"]["tenants"] == 1

        denied = await client.get(
            "/api/v1/platform/access/users",
            headers=scoped_headers,
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "AUTH_PERMISSION_DENIED"
    finally:
        await client.delete(
            f"/api/v1/platform/access/users/{user['id']}",
            headers=super_headers,
        )
        await client.delete(
            f"/api/v1/platform/access/roles/{role['id']}",
            headers=super_headers,
        )
        await platform.execute("delete from tenants where id=$1::uuid", outside_id)
        await platform.close()


async def test_tenant_capability_toggle_blocks_runtime_route(
    client: httpx.AsyncClient,
) -> None:
    super_login = await platform_login(client)
    super_headers = {"authorization": f"Bearer {super_login['access_token']}"}
    tenants_response = await client.get("/api/v1/platform/tenants", headers=super_headers)
    assert tenants_response.status_code == 200
    tenant = next(
        row
        for row in tenants_response.json()["data"]
        if row["slug"] == settings.dev_tenant_slug
    )

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.dev_tenant_admin_email,
            "password": settings.dev_tenant_admin_password,
        },
    )
    assert login.status_code == 200, login.text
    tenant_headers = {
        "authorization": f"Bearer {login.json()['data']['access_token']}"
    }

    disable = await client.put(
        f"/api/v1/platform/access/tenants/{tenant['id']}/capabilities/customers",
        headers=super_headers,
        json={"enabled": False, "config": {}},
    )
    assert disable.status_code == 200, disable.text
    try:
        denied = await client.get("/api/v1/customers", headers=tenant_headers)
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "TENANT_CAPABILITY_DISABLED"
    finally:
        enable = await client.put(
            f"/api/v1/platform/access/tenants/{tenant['id']}/capabilities/customers",
            headers=super_headers,
            json={"enabled": True, "config": {}},
        )
        assert enable.status_code == 200, enable.text

    allowed = await client.get("/api/v1/customers", headers=tenant_headers)
    assert allowed.status_code == 200, allowed.text
