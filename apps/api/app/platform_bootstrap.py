import asyncio

from sqlalchemy import text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import PlatformSession


async def bootstrap_platform_admin() -> None:
    email = settings.platform_admin_email
    password = settings.platform_admin_password
    if not email or not password:
        raise RuntimeError(
            "PLATFORM_ADMIN_EMAIL and PLATFORM_ADMIN_PASSWORD are required for production bootstrap"
        )

    normalized_email = email.lower()
    async with PlatformSession() as session:
        existing = (
            await session.execute(
                text(
                    """
                    select email,is_super_admin,is_active
                    from platform_users
                    where lower(email)=:email
                    limit 1
                    """
                ),
                {"email": normalized_email},
            )
        ).mappings().first()

        if len(password) < 12:
            if existing and bool(existing["is_super_admin"]) and bool(existing["is_active"]):
                print(
                    "Scheduler Pro platform admin already exists; "
                    "legacy PLATFORM_ADMIN_PASSWORD was not reapplied. "
                    "Configure a password with at least 12 characters before the next credential rotation."
                )
                return
            raise RuntimeError("PLATFORM_ADMIN_PASSWORD must contain at least 12 characters")

        await session.execute(
            text(
                """
                insert into platform_users(
                  email,password_hash,is_super_admin,is_active,
                  failed_login_attempts,locked_until,updated_at
                ) values(:email,:password_hash,true,true,0,null,now())
                on conflict(email) do update set
                  password_hash=excluded.password_hash,
                  is_super_admin=true,
                  is_active=true,
                  failed_login_attempts=0,
                  locked_until=null,
                  updated_at=now()
                """
            ),
            {"email": normalized_email, "password_hash": hash_password(password)},
        )
        await session.commit()
    print(f"Scheduler Pro platform admin ready: {normalized_email}")


if __name__ == "__main__":
    asyncio.run(bootstrap_platform_admin())
