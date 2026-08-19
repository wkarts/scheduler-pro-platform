import os
from uuid import uuid4

import asyncpg
import boto3
import httpx
import pytest

from app.cli import migrate_tenant
from app.core.config import settings
from app.core.security import hash_password

pytestmark = pytest.mark.integration

PLATFORM_MIGRATION_HEAD = "platform_0008"
TENANT_MIGRATION_HEAD = "tenant_0008_mail_mode"


async def tenant_login(client: httpx.AsyncClient, host: str = "localhost") -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        headers={"host": host},
        json={
            "email": settings.dev_tenant_admin_email,
            "password": settings.dev_tenant_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_bootstrap_created_platform_tenant_migrations_and_bucket() -> None:
    platform = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    try:
        platform_revision = await platform.fetchval("select version_num from alembic_version")
        row = await platform.fetchrow(
            """
            select td.database_name, td.database_user, td.password_ref, t.status
            from tenants t
            join tenant_databases td on td.tenant_id=t.id
            where t.slug=$1
            """,
            settings.dev_tenant_slug,
        )
        assert platform_revision == PLATFORM_MIGRATION_HEAD
        assert row is not None
        assert row["database_name"] == settings.dev_tenant_database
        assert row["password_ref"] == settings.dev_tenant_database_password_ref
        assert row["password_ref"] != settings.dev_tenant_database_password
        assert row["status"] == "ACTIVE"
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
        tenant_revision = await tenant.fetchval("select version_num from alembic_version")
        assert tenant_revision == TENANT_MIGRATION_HEAD
    finally:
        await tenant.close()

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    await __import__("asyncio").to_thread(s3.head_bucket, Bucket=settings.dev_tenant_bucket)


async def test_login_invalid_login_refresh_rotation_and_logout(client: httpx.AsyncClient) -> None:
    invalid = await client.post(
        "/api/v1/auth/login",
        json={"email": settings.dev_tenant_admin_email, "password": "incorrect-password"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    login = await tenant_login(client)
    assert login["access_token"]
    assert login["refresh_token"]
    assert "customers.read" in login["user"]["permissions"]

    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()["data"]
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"] != login["refresh_token"]

    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert reused.status_code == 401

    current = await tenant_login(client)
    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {current['access_token']}"},
        json={"refresh_token": current["refresh_token"]},
    )
    assert logout.status_code == 200


async def test_private_routes_and_platform_routes_are_protected(client: httpx.AsyncClient) -> None:
    tenant_private = await client.get("/api/v1/customers")
    assert tenant_private.status_code == 401

    platform_private = await client.get("/api/v1/platform/tenants")
    assert platform_private.status_code == 401

    super_login = await client.post(
        "/api/v1/auth/platform/login",
        json={
            "email": settings.dev_platform_admin_email,
            "password": settings.dev_platform_admin_password,
        },
    )
    assert super_login.status_code == 200, super_login.text
    token = super_login.json()["data"]["access_token"]
    tenants = await client.get(
        "/api/v1/platform/tenants", headers={"Authorization": f"Bearer {token}"}
    )
    assert tenants.status_code == 200
    assert tenants.json()["data"]


async def test_rbac_is_loaded_from_database_not_from_jwt(client: httpx.AsyncClient) -> None:
    tenant_auth = await tenant_login(client)
    token = tenant_auth["access_token"]

    allowed = await client.get(
        "/api/v1/customers", headers={"Authorization": f"Bearer {token}"}
    )
    assert allowed.status_code == 200

    tenant = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.dev_tenant_database_user,
        password=settings.dev_tenant_database_password,
        database=settings.dev_tenant_database,
    )
    try:
        await tenant.execute(
            """
            delete from role_permissions
            where role_id in (
              select ur.role_id
              from user_roles ur
              join users u on u.id=ur.user_id
              where u.email=$1
            )
              and permission_id=(select id from permissions where key='customers.read')
            """,
            settings.dev_tenant_admin_email,
        )
    finally:
        await tenant.close()

    denied = await client.get(
        "/api/v1/customers", headers={"Authorization": f"Bearer {token}"}
    )
    assert denied.status_code == 403

    # Restore permission for following integration tests.
    tenant = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.dev_tenant_database_user,
        password=settings.dev_tenant_database_password,
        database=settings.dev_tenant_database,
    )
    try:
        await tenant.execute(
            """
            insert into role_permissions(role_id, permission_id)
            select ur.role_id, p.id
            from user_roles ur
            join users u on u.id=ur.user_id
            join permissions p on p.key='customers.read'
            where u.email=$1
            on conflict do nothing
            """,
            settings.dev_tenant_admin_email,
        )
    finally:
        await tenant.close()


async def test_tenant_isolation_and_unknown_hostname(client: httpx.AsyncClient) -> None:
    platform = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    admin = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_admin_user,
        password=settings.postgres_admin_password,
        database="postgres",
    )
    tenant2_db = f"tenant_{uuid4().hex[:10]}"
    tenant2_user = f"user_{uuid4().hex[:10]}"
    tenant2_password = f"Password-{uuid4().hex}"
    tenant2_host = f"tenant2-{uuid4().hex[:8]}.localhost"
    tenant2_slug = f"tenant2-{uuid4().hex[:8]}"
    tenant2_id = None
    try:
        tenant2_id = await platform.fetchval(
            """
            insert into tenants(name, slug, status)
            values($1, $2, 'ACTIVE') returning id
            """,
            "Second Tenant",
            tenant2_slug,
        )
        await platform.execute(
            """
            insert into domains(tenant_id, hostname, status, is_primary, is_temporary)
            values($1, $2, 'ACTIVE', true, false)
            """,
            tenant2_id,
            tenant2_host,
        )
        await admin.execute(
            f'create role "{tenant2_user}" login password \'{tenant2_password}\''
        )
        await admin.execute(f'create database "{tenant2_db}" owner "{tenant2_user}"')
        await migrate_tenant(tenant2_db, tenant2_user, tenant2_password)

        second = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=tenant2_user,
            password=tenant2_password,
            database=tenant2_db,
        )
        try:
            await second.execute(
                "insert into customers(name) values($1)", "Tenant Two Customer"
            )
        finally:
            await second.close()

        dev = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.dev_tenant_database_user,
            password=settings.dev_tenant_database_password,
            database=settings.dev_tenant_database,
        )
        try:
            assert await dev.fetchval(
                "select count(*) from customers where name='Tenant Two Customer'"
            ) == 0
        finally:
            await dev.close()

        unknown = await client.post(
            "/api/v1/auth/login",
            headers={"host": f"unknown-{uuid4().hex}.localhost"},
            json={
                "email": settings.dev_tenant_admin_email,
                "password": settings.dev_tenant_admin_password,
            },
        )
        assert unknown.status_code == 404
    finally:
        if tenant2_id:
            await platform.execute("delete from tenants where id=$1", tenant2_id)
        try:
            await admin.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity where datname=$1",
                tenant2_db,
            )
            await admin.execute(f'drop database if exists "{tenant2_db}"')
            await admin.execute(f'drop role if exists "{tenant2_user}"')
        finally:
            await admin.close()
            await platform.close()


async def test_suspended_tenant_cannot_open_session(client: httpx.AsyncClient) -> None:
    platform = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    try:
        await platform.execute(
            "update tenants set status='SUSPENDED' where slug=$1", settings.dev_tenant_slug
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": settings.dev_tenant_admin_email,
                "password": settings.dev_tenant_admin_password,
            },
        )
        assert response.status_code == 403
    finally:
        await platform.execute(
            "update tenants set status='ACTIVE' where slug=$1", settings.dev_tenant_slug
        )
        await platform.close()


async def test_readiness_checks_real_dependencies(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert payload["ready"] is True
    for key in ("postgres_platform", "redis", "rabbitmq", "storage", "tenant"):
        assert payload["checks"][key]["status"] in {"ok", "not_applicable"}
