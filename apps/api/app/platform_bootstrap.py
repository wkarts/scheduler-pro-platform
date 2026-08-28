import asyncio

from sqlalchemy import text

from app.cli import migrate_all_tenants
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import PlatformSession
from app.services.builtin_template_package_service import sync_builtin_template_packages


async def bootstrap_platform_admin() -> None:
    email = settings.platform_admin_email
    password = settings.platform_admin_password
    if not email or not password:
        raise RuntimeError(
            "PLATFORM_ADMIN_EMAIL and PLATFORM_ADMIN_PASSWORD are required for production bootstrap"
        )

    normalized_email = email.lower()
    async with PlatformSession() as session:
        if len(password) < 12:
            existing_superadmin = (
                await session.execute(
                    text(
                        """
                        select email,is_super_admin,is_active
                        from platform_users
                        where is_super_admin=true and is_active=true
                        order by case when lower(email)=:email then 0 else 1 end
                        limit 1
                        """
                    ),
                    {"email": normalized_email},
                )
            ).mappings().first()

            if existing_superadmin:
                preserved_email = str(existing_superadmin["email"]).lower()
                print(
                    "Scheduler Pro active platform superadmin already exists "
                    f"({preserved_email}); legacy PLATFORM_ADMIN_PASSWORD was not reapplied. "
                    "Configure a password with at least 12 characters before the next credential rotation."
                )
                return

            raise RuntimeError(
                "PLATFORM_ADMIN_PASSWORD must contain at least 12 characters; "
                "no active platform superadmin exists to preserve"
            )

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


async def bootstrap_template_library() -> None:
    async with PlatformSession() as session:
        result = await sync_builtin_template_packages(session)
    changed = sum(1 for item in result["templates"] if item.get("updated"))
    print(f"Scheduler Pro official template library 2.3.1 ready: {changed} surface(s) synchronized")


async def bootstrap_platform() -> None:
    # Mantém compatibilidade com deployments antigos que ainda não possuam o
    # serviço one-shot scheduler-tenant-migrate no Compose. Em deployments atuais
    # este segundo passe é idempotente e garante que API/workers nunca iniciem
    # contra tenant databases sem o Alembic head esperado pela imagem nova.
    await migrate_all_tenants()
    await bootstrap_platform_admin()
    await bootstrap_template_library()


if __name__ == "__main__":
    asyncio.run(bootstrap_platform())
