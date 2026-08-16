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

TENANT_MIGRATION_HEAD = "tenant_0003_scheduler_engine"


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
        assert platform_revision == "platform_0004"
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
    rotated = refreshed.json()["data"]
    assert rotated["refresh_token"] != login["refresh_token"]

    reused = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "AUTH_REFRESH_REUSED"

    another_login = await tenant_login(client)
    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"authorization": f"Bearer {another_login['access_token']}"},
        json={"refresh_token": another_login["refresh_token"]},
    )
    assert logout.status_code == 200
    rejected = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": another_login["refresh_token"]},
    )
    assert rejected.status_code == 401


async def test_private_routes_and_platform_routes_are_protected(client: httpx.AsyncClient) -> None:
    unauthenticated = await client.get("/api/v1/customers")
    assert unauthenticated.status_code == 401

    tenant = await tenant_login(client)
    tenant_customers = await client.get(
        "/api/v1/customers",
        headers={"authorization": f"Bearer {tenant['access_token']}"},
    )
    assert tenant_customers.status_code == 200

    tenant_on_platform = await client.get(
        "/api/v1/platform/dashboard",
        headers={"authorization": f"Bearer {tenant['access_token']}"},
    )
    assert tenant_on_platform.status_code == 403

    platform_login = await client.post(
        "/api/v1/auth/platform/login",
        json={
            "email": settings.dev_platform_admin_email,
            "password": settings.dev_platform_admin_password,
        },
    )
    assert platform_login.status_code == 200, platform_login.text
    platform_token = platform_login.json()["data"]["access_token"]
    dashboard = await client.get(
        "/api/v1/platform/dashboard",
        headers={"authorization": f"Bearer {platform_token}"},
    )
    assert dashboard.status_code == 200


async def test_rbac_is_loaded_from_database_not_from_jwt(client: httpx.AsyncClient) -> None:
    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.dev_tenant_database_user,
        password=settings.dev_tenant_database_password,
        database=settings.dev_tenant_database,
    )
    email = f"readonly-{uuid4().hex}@tenant.example"
    password = "ReadOnly-Password-2026!"
    try:
        user_id = await conn.fetchval(
            """
            insert into users(email, password_hash, display_name, is_active)
            values($1, $2, 'Read Only', true) returning id::text
            """,
            email,
            hash_password(password),
        )
        role_id = await conn.fetchval(
            """
            insert into roles(name, description)
            values($1, 'Integration test read-only role') returning id::text
            """,
            f"readonly-{uuid4().hex}",
        )
        permission_id = await conn.fetchval("select id::text from permissions where key='customers.read'")
        await conn.execute(
            "insert into user_roles(user_id, role_id) values($1::uuid, $2::uuid)",
            user_id,
            role_id,
        )
        await conn.execute(
            """
            insert into role_permissions(role_id, permission_id)
            values($1::uuid, $2::uuid)
            """,
            role_id,
            permission_id,
        )
    finally:
        await conn.close()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    headers = {"authorization": f"Bearer {token}"}
    assert (await client.get("/api/v1/customers", headers=headers)).status_code == 200
    denied = await client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Denied Customer"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "AUTH_PERMISSION_DENIED"


async def _prepare_second_tenant() -> tuple[str, str, str, str]:
    db_name = "tenant_test_b"
    db_user = "tenant_test_b_user"
    db_password = "tenant_test_b_password"
    domain = "tenant-b.local"
    os.environ["TENANT_TEST_B_DATABASE_PASSWORD"] = db_password

    admin = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_admin_user,
        password=settings.postgres_admin_password,
        database=settings.postgres_db,
    )
    try:
        literal = await admin.fetchval("select quote_literal($1)", db_password)
        role_exists = await admin.fetchval("select exists(select 1 from pg_roles where rolname=$1)", db_user)
        if role_exists:
            await admin.execute(f'alter role "{db_user}" with login password {literal}')
        else:
            await admin.execute(f'create role "{db_user}" login password {literal}')
        db_exists = await admin.fetchval(
            "select exists(select 1 from pg_database where datname=$1)", db_name
        )
        if not db_exists:
            await admin.execute(f'create database "{db_name}" owner "{db_user}"')
    finally:
        await admin.close()

    migrate_tenant(db_name, db_user, db_password)

    platform = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    try:
        tenant_id = await platform.fetchval("select id::text from tenants where slug='integration-b'")
        if tenant_id is None:
            tenant_id = await platform.fetchval(
                """
                insert into tenants(name, slug, status, timezone, settings)
                values('Integration Tenant B', 'integration-b', 'ACTIVE', 'America/Bahia', '{}')
                returning id::text
                """
            )
        await platform.execute(
            """
            insert into tenant_databases(
                tenant_id, database_name, database_user, password_ref, credential_version
            ) values($1::uuid, $2, $3, 'secret://env/TENANT_TEST_B_DATABASE_PASSWORD', 1)
            on conflict(tenant_id) do update set
                database_name=excluded.database_name,
                database_user=excluded.database_user,
                password_ref=excluded.password_ref
            """,
            tenant_id,
            db_name,
            db_user,
        )
        await platform.execute(
            """
            insert into tenant_storage(tenant_id, bucket)
            values($1::uuid, 'tenant-test-b')
            on conflict(tenant_id) do update set bucket=excluded.bucket
            """,
            tenant_id,
        )
        await platform.execute(
            """
            insert into domains(tenant_id, hostname, is_primary, is_temporary, status, validation)
            values($1::uuid, $2, true, true, 'ACTIVE', '{}')
            on conflict(hostname) do update set tenant_id=excluded.tenant_id, status='ACTIVE'
            """,
            tenant_id,
            domain,
        )
    finally:
        await platform.close()

    tenant = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=db_user,
        password=db_password,
        database=db_name,
    )
    email = "admin@tenant-b.example"
    password = "Tenant-B-Password-2026!"
    try:
        role_id = await tenant.fetchval(
            """
            insert into roles(name, description) values('tenant-admin', 'Tenant B admin')
            on conflict(name) do update set description=excluded.description returning id::text
            """
        )
        user_id = await tenant.fetchval(
            """
            insert into users(email, password_hash, display_name, is_active)
            values($1, $2, 'Tenant B Admin', true)
            on conflict(email) do update set password_hash=excluded.password_hash, is_active=true
            returning id::text
            """,
            email,
            hash_password(password),
        )
        for permission in ("customers.read", "customers.manage"):
            permission_id = await tenant.fetchval(
                """
                insert into permissions(key, description) values($1, $2)
                on conflict(key) do update set description=excluded.description returning id::text
                """,
                permission,
                permission,
            )
            await tenant.execute(
                """
                insert into role_permissions(role_id, permission_id)
                values($1::uuid, $2::uuid) on conflict do nothing
                """,
                role_id,
                permission_id,
            )
        await tenant.execute(
            """
            insert into user_roles(user_id, role_id)
            values($1::uuid, $2::uuid) on conflict do nothing
            """,
            user_id,
            role_id,
        )
    finally:
        await tenant.close()
    return domain, email, password, db_name


async def test_tenant_isolation_and_unknown_hostname(client: httpx.AsyncClient) -> None:
    unknown = await client.post(
        "/api/v1/auth/login",
        headers={"host": "unknown-tenant.local"},
        json={
            "email": settings.dev_tenant_admin_email,
            "password": settings.dev_tenant_admin_password,
        },
    )
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "TENANT_NOT_FOUND"

    domain, tenant_b_email, tenant_b_password, _ = await _prepare_second_tenant()
    tenant_a = await tenant_login(client)
    tenant_b_response = await client.post(
        "/api/v1/auth/login",
        headers={"host": domain},
        json={"email": tenant_b_email, "password": tenant_b_password},
    )
    assert tenant_b_response.status_code == 200, tenant_b_response.text
    tenant_b = tenant_b_response.json()["data"]

    cross_tenant = await client.get(
        "/api/v1/customers",
        headers={
            "host": domain,
            "authorization": f"Bearer {tenant_a['access_token']}",
        },
    )
    assert cross_tenant.status_code == 403
    assert cross_tenant.json()["error"]["code"] == "TENANT_CONTEXT_MISMATCH"

    name_a = f"Tenant A {uuid4().hex}"
    name_b = f"Tenant B {uuid4().hex}"
    created_a = await client.post(
        "/api/v1/customers",
        headers={"authorization": f"Bearer {tenant_a['access_token']}"},
        json={"name": name_a},
    )
    created_b = await client.post(
        "/api/v1/customers",
        headers={"host": domain, "authorization": f"Bearer {tenant_b['access_token']}"},
        json={"name": name_b},
    )
    assert created_a.status_code == 200
    assert created_b.status_code == 200

    list_a = await client.get(
        "/api/v1/customers",
        headers={"authorization": f"Bearer {tenant_a['access_token']}"},
    )
    list_b = await client.get(
        "/api/v1/customers",
        headers={"host": domain, "authorization": f"Bearer {tenant_b['access_token']}"},
    )
    names_a = {row["name"] for row in list_a.json()["data"]}
    names_b = {row["name"] for row in list_b.json()["data"]}
    assert name_a in names_a and name_a not in names_b
    assert name_b in names_b and name_b not in names_a


async def test_suspended_tenant_cannot_open_session(client: httpx.AsyncClient) -> None:
    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )
    try:
        await conn.execute("update tenants set status='SUSPENDED' where slug=$1", settings.dev_tenant_slug)
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": settings.dev_tenant_admin_email,
                "password": settings.dev_tenant_admin_password,
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "TENANT_SUSPENDED"
    finally:
        await conn.execute("update tenants set status='ACTIVE' where slug=$1", settings.dev_tenant_slug)
        await conn.close()


async def test_readiness_checks_real_dependencies(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["ready"] is True
    assert data["checks"]["postgres_platform"]["status"] == "ok"
    assert data["checks"]["tenant"]["status"] == "ok"
    assert data["checks"]["redis"]["status"] == "ok"
    assert data["checks"]["rabbitmq"]["status"] == "ok"
    assert data["checks"]["storage"]["status"] == "ok"
