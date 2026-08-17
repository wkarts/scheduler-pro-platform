import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.security import hash_opaque_token
from app.db.session import PlatformSession, get_tenant_engine
from app.services.password_recovery_service import (
    PlatformPasswordRecoveryService,
    TenantPasswordRecoveryService,
)
from app.services.tenant_resolver import TenantResolver

pytestmark = pytest.mark.integration


async def test_platform_password_reset_is_one_time_and_revokes_sessions(
    client: httpx.AsyncClient,
) -> None:
    new_password = "Recovered-Platform-2026!"
    async with PlatformSession() as session:
        original_hash = (
            await session.execute(
                text(
                    """
                    select password_hash
                    from platform_users
                    where lower(email)=:email
                    """
                ),
                {"email": settings.dev_platform_admin_email.lower()},
            )
        ).scalar_one()
        created = await PlatformPasswordRecoveryService(session).create_reset_token(
            settings.dev_platform_admin_email,
            ip_address="127.0.0.1",
            correlation_id="integration-platform-reset",
        )
        assert created is not None
        _, raw_token = created
        stored_hash = (
            await session.execute(
                text(
                    """
                    select token_hash
                    from platform_password_reset_tokens
                    where user_id=(
                        select id from platform_users where lower(email)=:email
                    )
                    order by created_at desc
                    limit 1
                    """
                ),
                {"email": settings.dev_platform_admin_email.lower()},
            )
        ).scalar_one()
        assert stored_hash == hash_opaque_token(raw_token)
        assert raw_token != stored_hash

    try:
        reset = await client.post(
            "/api/v1/auth/platform/password/reset",
            json={"token": raw_token, "new_password": new_password},
        )
        assert reset.status_code == 200, reset.text

        login = await client.post(
            "/api/v1/auth/platform/login",
            json={
                "email": settings.dev_platform_admin_email,
                "password": new_password,
            },
        )
        assert login.status_code == 200, login.text

        reused = await client.post(
            "/api/v1/auth/platform/password/reset",
            json={"token": raw_token, "new_password": "Another-Platform-2026!"},
        )
        assert reused.status_code == 400
        assert reused.json()["error"]["code"] == "PASSWORD_RESET_INVALID"
    finally:
        async with PlatformSession() as session:
            await session.execute(
                text(
                    """
                    update platform_users
                    set password_hash=:password_hash,
                        failed_login_attempts=0,
                        locked_until=null,
                        updated_at=now()
                    where lower(email)=:email
                    """
                ),
                {
                    "email": settings.dev_platform_admin_email.lower(),
                    "password_hash": original_hash,
                },
            )
            await session.execute(
                text(
                    """
                    delete from platform_password_reset_tokens
                    where user_id=(
                        select id from platform_users where lower(email)=:email
                    )
                    """
                ),
                {"email": settings.dev_platform_admin_email.lower()},
            )
            await session.commit()


async def test_tenant_password_reset_is_one_time_and_keeps_tenant_scope(
    client: httpx.AsyncClient,
) -> None:
    async with PlatformSession() as platform:
        context = await TenantResolver(platform).resolve("localhost")

    engine = await get_tenant_engine(context)
    factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    new_password = "Recovered-Tenant-2026!"

    async with factory() as session:
        original_hash = (
            await session.execute(
                text(
                    """
                    select password_hash
                    from users
                    where lower(email)=:email
                    """
                ),
                {"email": settings.dev_tenant_admin_email.lower()},
            )
        ).scalar_one()
        created = await TenantPasswordRecoveryService(session).create_reset_token(
            settings.dev_tenant_admin_email,
            ip_address="127.0.0.1",
            correlation_id="integration-tenant-reset",
        )
        assert created is not None
        _, raw_token = created
        stored_hash = (
            await session.execute(
                text(
                    """
                    select token_hash
                    from password_reset_tokens
                    where user_id=(
                        select id from users where lower(email)=:email
                    )
                    order by created_at desc
                    limit 1
                    """
                ),
                {"email": settings.dev_tenant_admin_email.lower()},
            )
        ).scalar_one()
        assert stored_hash == hash_opaque_token(raw_token)
        assert raw_token != stored_hash

    try:
        reset = await client.post(
            "/api/v1/auth/password/reset",
            headers={"host": "localhost"},
            json={"token": raw_token, "new_password": new_password},
        )
        assert reset.status_code == 200, reset.text

        login = await client.post(
            "/api/v1/auth/login",
            headers={"host": "localhost"},
            json={
                "email": settings.dev_tenant_admin_email,
                "password": new_password,
            },
        )
        assert login.status_code == 200, login.text

        wrong_tenant = await client.post(
            "/api/v1/auth/password/reset",
            headers={"host": "unknown-tenant.local"},
            json={"token": raw_token, "new_password": "Other-Tenant-2026!"},
        )
        assert wrong_tenant.status_code == 404
        assert wrong_tenant.json()["error"]["code"] == "TENANT_NOT_FOUND"

        reused = await client.post(
            "/api/v1/auth/password/reset",
            headers={"host": "localhost"},
            json={"token": raw_token, "new_password": "Other-Tenant-2026!"},
        )
        assert reused.status_code == 400
        assert reused.json()["error"]["code"] == "PASSWORD_RESET_INVALID"
    finally:
        async with factory() as session:
            await session.execute(
                text(
                    """
                    update users
                    set password_hash=:password_hash,
                        failed_login_attempts=0,
                        locked_until=null,
                        updated_at=now()
                    where lower(email)=:email
                    """
                ),
                {
                    "email": settings.dev_tenant_admin_email.lower(),
                    "password_hash": original_hash,
                },
            )
            await session.execute(
                text(
                    """
                    delete from password_reset_tokens
                    where user_id=(
                        select id from users where lower(email)=:email
                    )
                    """
                ),
                {"email": settings.dev_tenant_admin_email.lower()},
            )
            await session.commit()
