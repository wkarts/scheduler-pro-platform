import asyncpg
import httpx
import pytest

from app.core.config import settings

pytestmark = pytest.mark.integration


async def test_inactive_domain_cannot_resolve_tenant(client: httpx.AsyncClient) -> None:
    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    try:
        await conn.execute("update domains set status='PENDING' where hostname='localhost'")
        response = await client.post(
            "/api/v1/auth/login",
            headers={"host": "localhost"},
            json={
                "email": settings.dev_tenant_admin_email,
                "password": settings.dev_tenant_admin_password,
            },
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DOMAIN_NOT_ACTIVE"
    finally:
        await conn.execute("update domains set status='ACTIVE' where hostname='localhost'")
        await conn.close()
