import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg
import boto3
from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.core.security import hash_password

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PERMISSIONS = [
    "appointments.read",
    "appointments.create",
    "appointments.update",
    "appointments.cancel",
    "customers.read",
    "customers.manage",
    "services.manage",
    "professionals.manage",
    "notifications.manage",
    "whatsapp.manage",
    "landing_pages.manage",
    "branding.manage",
    "reports.read",
    "tenant.manage",
]


def _identifier(value: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError("Unsafe PostgreSQL identifier.")
    return f'"{value}"'


async def _connect(
    database: str,
    *,
    user: str | None = None,
    password: str | None = None,
) -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=user or settings.postgres_user,
        password=password or settings.postgres_password,
        database=database,
    )


def _alembic_config(filename: str) -> Config:
    return Config(str(ROOT / filename))


def migrate_platform() -> None:
    command.upgrade(_alembic_config("alembic.ini"), "head")


def migrate_tenant(database: str, user: str, password: str) -> None:
    previous = {
        "ALEMBIC_TENANT_DATABASE": os.environ.get("ALEMBIC_TENANT_DATABASE"),
        "ALEMBIC_TENANT_USER": os.environ.get("ALEMBIC_TENANT_USER"),
        "ALEMBIC_TENANT_PASSWORD": os.environ.get("ALEMBIC_TENANT_PASSWORD"),
    }
    os.environ["ALEMBIC_TENANT_DATABASE"] = database
    os.environ["ALEMBIC_TENANT_USER"] = user
    os.environ["ALEMBIC_TENANT_PASSWORD"] = password
    try:
        command.upgrade(_alembic_config("alembic-tenant.ini"), "head")
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def ensure_dev_database() -> None:
    conn = await _connect(
        settings.postgres_db,
        user=settings.postgres_admin_user,
        password=settings.postgres_admin_password,
    )
    try:
        role = settings.dev_tenant_database_user
        password_literal = await conn.fetchval("select quote_literal($1)", settings.dev_tenant_database_password)
        role_exists = await conn.fetchval("select exists(select 1 from pg_roles where rolname=$1)", role)
        if role_exists:
            await conn.execute(f"alter role {_identifier(role)} with login password {password_literal}")
        else:
            await conn.execute(f"create role {_identifier(role)} login password {password_literal}")

        db_exists = await conn.fetchval(
            "select exists(select 1 from pg_database where datname=$1)",
            settings.dev_tenant_database,
        )
        if not db_exists:
            await conn.execute(
                f"create database {_identifier(settings.dev_tenant_database)} "
                f"owner {_identifier(settings.dev_tenant_database_user)}"
            )
    finally:
        await conn.close()


async def seed_platform() -> str:
    conn = await _connect(settings.postgres_db)
    try:
        tenant_id = await conn.fetchval(
            "select id::text from tenants where slug=$1",
            settings.dev_tenant_slug,
        )
        if tenant_id is None:
            tenant_id = await conn.fetchval(
                """
                insert into tenants(name, slug, status, timezone, settings)
                values($1, $2, 'ACTIVE', 'America/Bahia', '{}'::jsonb)
                returning id::text
                """,
                settings.dev_tenant_name,
                settings.dev_tenant_slug,
            )
        else:
            await conn.execute("update tenants set status='ACTIVE' where id=$1::uuid", tenant_id)

        await conn.execute(
            """
            insert into tenant_databases(
                tenant_id, database_name, database_user, password_ref, credential_version
            ) values($1::uuid, $2, $3, $4, 1)
            on conflict(tenant_id) do update set
                database_name=excluded.database_name,
                database_user=excluded.database_user,
                password_ref=excluded.password_ref
            """,
            tenant_id,
            settings.dev_tenant_database,
            settings.dev_tenant_database_user,
            settings.dev_tenant_database_password_ref,
        )
        await conn.execute(
            """
            insert into tenant_storage(tenant_id, bucket)
            values($1::uuid, $2)
            on conflict(tenant_id) do update set bucket=excluded.bucket
            """,
            tenant_id,
            settings.dev_tenant_bucket,
        )
        for hostname, primary in (("localhost", True), ("127.0.0.1", False)):
            await conn.execute(
                """
                insert into domains(tenant_id, hostname, is_primary, is_temporary, status, validation)
                values($1::uuid, $2, $3, true, 'ACTIVE', '{}'::jsonb)
                on conflict(hostname) do nothing
                """,
                tenant_id,
                hostname,
                primary,
            )

        await conn.execute(
            """
            insert into platform_users(
                email, password_hash, is_super_admin, is_active,
                failed_login_attempts, locked_until, updated_at
            ) values($1, $2, true, true, 0, null, now())
            on conflict(email) do update set
                password_hash=excluded.password_hash,
                is_super_admin=true,
                is_active=true,
                failed_login_attempts=0,
                locked_until=null,
                updated_at=now()
            """,
            settings.dev_platform_admin_email.lower(),
            hash_password(settings.dev_platform_admin_password),
        )
        return tenant_id
    finally:
        await conn.close()


async def seed_tenant() -> None:
    conn = await _connect(
        settings.dev_tenant_database,
        user=settings.dev_tenant_database_user,
        password=settings.dev_tenant_database_password,
    )
    try:
        role_id = await conn.fetchval(
            """
            insert into roles(name, description) values('tenant-admin', 'Administrador do tenant')
            on conflict(name) do update set description=excluded.description
            returning id::text
            """
        )
        permission_ids: list[str] = []
        for permission in PERMISSIONS:
            permission_id = await conn.fetchval(
                """
                insert into permissions(key, description) values($1, $1)
                on conflict(key) do update set description=excluded.description
                returning id::text
                """,
                permission,
            )
            permission_ids.append(permission_id)

        user_id = await conn.fetchval(
            """
            insert into users(
                email, password_hash, display_name, is_active,
                failed_login_attempts, locked_until, updated_at
            ) values($1, $2, 'Tenant Administrator', true, 0, null, now())
            on conflict(email) do update set
                password_hash=excluded.password_hash,
                is_active=true,
                failed_login_attempts=0,
                locked_until=null,
                updated_at=now()
            returning id::text
            """,
            settings.dev_tenant_admin_email.lower(),
            hash_password(settings.dev_tenant_admin_password),
        )
        await conn.execute(
            "insert into user_roles(user_id, role_id) values($1::uuid, $2::uuid) on conflict do nothing",
            user_id,
            role_id,
        )
        for permission_id in permission_ids:
            await conn.execute(
                """
                insert into role_permissions(role_id, permission_id)
                values($1::uuid, $2::uuid) on conflict do nothing
                """,
                role_id,
                permission_id,
            )
    finally:
        await conn.close()


def ensure_dev_bucket() -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    existing = {bucket["Name"] for bucket in s3.list_buckets().get("Buckets", [])}
    if settings.dev_tenant_bucket not in existing:
        s3.create_bucket(Bucket=settings.dev_tenant_bucket)


async def bootstrap_dev() -> None:
    if settings.app_env != "development":
        raise RuntimeError("bootstrap-dev is restricted to APP_ENV=development")
    await ensure_dev_database()
    migrate_platform()
    await seed_platform()
    migrate_tenant(
        settings.dev_tenant_database,
        settings.dev_tenant_database_user,
        settings.dev_tenant_database_password,
    )
    await seed_tenant()
    await asyncio.to_thread(ensure_dev_bucket)
    print("Scheduler Pro development bootstrap completed.")


async def main() -> None:
    command_name = sys.argv[1] if len(sys.argv) > 1 else "help"
    if command_name == "migrate-platform":
        migrate_platform()
        return
    if command_name == "migrate-tenant" and len(sys.argv) >= 3:
        database = sys.argv[2]
        user = os.getenv("ALEMBIC_TENANT_USER")
        password = os.getenv("ALEMBIC_TENANT_PASSWORD")
        if database == settings.dev_tenant_database:
            user = user or settings.dev_tenant_database_user
            password = password or settings.dev_tenant_database_password
        if not user or not password:
            raise RuntimeError("ALEMBIC_TENANT_USER and ALEMBIC_TENANT_PASSWORD are required")
        migrate_tenant(database, user, password)
        return
    if command_name == "bootstrap-dev":
        await bootstrap_dev()
        return
    print(
        "Usage: python -m app.cli migrate-platform | migrate-tenant <database> | bootstrap-dev",
        file=sys.stderr,
    )
    raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
