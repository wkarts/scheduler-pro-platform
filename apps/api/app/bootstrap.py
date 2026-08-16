import asyncio
import sys

import asyncpg

from app.core.config import settings
from app.core.security import hash_password


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
    )


async def bootstrap_platform_admin() -> None:
    email = settings.effective_platform_admin_email
    password = settings.effective_platform_admin_password
    if not email or not password:
        raise RuntimeError("PLATFORM_ADMIN_EMAIL/PLATFORM_ADMIN_PASSWORD não configurados.")
    conn = await _connect()
    try:
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
            email,
            hash_password(password),
        )
    finally:
        await conn.close()
    print(f"Platform admin ready: {email}")


async def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "platform-admin"
    if command == "platform-admin":
        await bootstrap_platform_admin()
        return
    raise SystemExit("Usage: python -m app.bootstrap platform-admin")


if __name__ == "__main__":
    asyncio.run(main())
