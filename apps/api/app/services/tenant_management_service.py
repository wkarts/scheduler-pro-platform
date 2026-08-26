from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.security import hash_password
from app.core.secrets import seal_secret
from app.core.tenant_context import DEFAULT_TENANT_STORAGE_QUOTA_BYTES
from app.db.models_platform import Tenant
from app.db.session import get_tenant_engine
from app.services.observability_service import ObservabilityService
from app.services.tenant_resolver import TenantResolver


class TenantManagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.logs = ObservabilityService(session)

    async def _tenant(self, tenant_id: str) -> Tenant:
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            raise APIError("TENANT_NOT_FOUND", "Tenant não encontrado.", 404)
        return tenant

    @staticmethod
    def _storage_quota_bytes(tenant: Tenant) -> int:
        raw = (tenant.settings or {}).get("storage_quota_bytes")
        value: int = DEFAULT_TENANT_STORAGE_QUOTA_BYTES
        if raw is not None:
            try:
                value = int(str(raw))
            except (TypeError, ValueError):
                value = DEFAULT_TENANT_STORAGE_QUOTA_BYTES
        return int(
            min(
                max(value, 128 * 1024 * 1024),
                1024 * 1024 * 1024 * 1024,
            )
        )

    async def _primary_hostname(self, tenant_id: str) -> str | None:
        return (
            await self.session.execute(
                text(
                    """
                    select hostname
                    from domains
                    where tenant_id=cast(:tenant_id as uuid)
                    order by is_primary desc, is_temporary desc, hostname asc
                    limit 1
                    """
                ),
                {"tenant_id": tenant_id},
            )
        ).scalar_one_or_none()

    async def _principal_admin(self, tenant: Tenant) -> dict[str, Any] | None:
        context = await TenantResolver(self.session).resolve_by_id(
            str(tenant.id),
            require_active=False,
        )
        engine = await get_tenant_engine(context)
        preferred_email = str(tenant.settings.get("admin_email") or "").strip().lower()

        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        """
                        select u.id::text, u.email, u.display_name, u.is_active, u.created_at
                        from users u
                        where exists(
                          select 1
                          from user_roles ur
                          join roles r on r.id=ur.role_id
                          where ur.user_id=u.id and r.name='tenant-admin'
                        )
                        order by case when lower(u.email)=:preferred_email then 0 else 1 end,
                                 u.created_at asc
                        limit 1
                        """
                    ),
                    {"preferred_email": preferred_email},
                )
            ).mappings().first()
            if row is None and preferred_email:
                row = (
                    await connection.execute(
                        text(
                            """
                            select id::text, email, display_name, is_active, created_at
                            from users
                            where lower(email)=:preferred_email
                            limit 1
                            """
                        ),
                        {"preferred_email": preferred_email},
                    )
                ).mappings().first()
        return dict(row) if row is not None else None

    async def snapshot(self, tenant_id: str) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        principal_admin: dict[str, Any] | None
        admin_error: dict[str, Any] | None = None
        try:
            principal_admin = await self._principal_admin(tenant)
        except Exception as exc:  # noqa: BLE001 - diagnóstico operacional do tenant
            principal_admin = None
            admin_error = {
                "type": exc.__class__.__name__,
                "message": str(exc),
            }
        quota_bytes = self._storage_quota_bytes(tenant)
        context = await TenantResolver(self.session).resolve_by_id(
            str(tenant.id),
            require_active=False,
        )
        return {
            "tenant": {
                "id": str(tenant.id),
                "name": tenant.name,
                "slug": tenant.slug,
                "status": tenant.status,
                "timezone": tenant.timezone,
                "primary_hostname": await self._primary_hostname(str(tenant.id)),
                "created_at": tenant.created_at,
            },
            "storage": {
                "bucket": context.storage_bucket,
                "quota_bytes": quota_bytes,
                "quota_mb": quota_bytes // (1024 * 1024),
                "default_quota_mb": DEFAULT_TENANT_STORAGE_QUOTA_BYTES // (1024 * 1024),
            },
            "principal_admin": principal_admin,
            "principal_admin_error": admin_error,
            "slug_editable": False,
            "slug_note": (
                "O código do tenant é imutável após o provisionamento porque identifica banco, "
                "storage, domínios e perfis de distribuição."
            ),
        }

    async def update_tenant(
        self,
        tenant_id: str,
        *,
        name: str | None = None,
        timezone: str | None = None,
        storage_quota_mb: int | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        before_quota = self._storage_quota_bytes(tenant)
        before = {
            "name": tenant.name,
            "timezone": tenant.timezone,
            "storage_quota_bytes": before_quota,
        }
        if name is not None:
            tenant.name = name.strip()
        if timezone is not None:
            tenant.timezone = timezone.strip()
        if storage_quota_mb is not None:
            settings_value = dict(tenant.settings or {})
            settings_value["storage_quota_bytes"] = storage_quota_mb * 1024 * 1024
            tenant.settings = settings_value
        after = {
            "name": tenant.name,
            "timezone": tenant.timezone,
            "storage_quota_bytes": self._storage_quota_bytes(tenant),
        }
        await self.logs.record_platform_log(
            tenant_id=str(tenant.id),
            source="admin",
            service="control-plane",
            event="tenant_updated",
            message="Dados cadastrais e limites do tenant atualizados pelo Control Plane.",
            actor=actor,
            details={"before": before, "after": after},
        )
        await self.session.commit()
        return await self.snapshot(tenant_id)

    async def update_principal_admin(
        self,
        tenant_id: str,
        *,
        email: str | None = None,
        password: str | None = None,
        display_name: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        tenant = await self._tenant(tenant_id)
        current = await self._principal_admin(tenant)
        if current is None:
            raise APIError(
                "TENANT_PRINCIPAL_ADMIN_NOT_FOUND",
                "O administrador principal do tenant ainda não foi provisionado.",
                409,
            )

        target_email = (email or str(current["email"])).strip().lower()
        target_display_name = (
            display_name.strip()
            if display_name is not None and display_name.strip()
            else str(current.get("display_name") or "Administrador")
        )
        context = await TenantResolver(self.session).resolve_by_id(
            str(tenant.id),
            require_active=False,
        )
        engine = await get_tenant_engine(context)

        async with engine.begin() as connection:
            conflict = (
                await connection.execute(
                    text(
                        """
                        select id::text
                        from users
                        where lower(email)=:email and id<>cast(:user_id as uuid)
                        limit 1
                        """
                    ),
                    {"email": target_email, "user_id": str(current["id"])},
                )
            ).scalar_one_or_none()
            if conflict is not None:
                raise APIError(
                    "TENANT_ADMIN_EMAIL_IN_USE",
                    "Já existe outro usuário com este e-mail no tenant.",
                    409,
                )

            if password:
                await connection.execute(
                    text(
                        """
                        update users
                        set email=:email,
                            display_name=:display_name,
                            password_hash=:password_hash,
                            is_active=true,
                            failed_login_attempts=0,
                            locked_until=null,
                            updated_at=now()
                        where id=cast(:user_id as uuid)
                        """
                    ),
                    {
                        "email": target_email,
                        "display_name": target_display_name,
                        "password_hash": hash_password(password),
                        "user_id": str(current["id"]),
                    },
                )
                await connection.execute(
                    text(
                        """
                        update user_sessions
                        set revoked_at=coalesce(revoked_at, now())
                        where user_id=cast(:user_id as uuid)
                        """
                    ),
                    {"user_id": str(current["id"])},
                )
                await connection.execute(
                    text(
                        """
                        update refresh_tokens
                        set revoked_at=coalesce(revoked_at, now())
                        where user_id=cast(:user_id as uuid)
                        """
                    ),
                    {"user_id": str(current["id"])},
                )
            else:
                await connection.execute(
                    text(
                        """
                        update users
                        set email=:email,
                            display_name=:display_name,
                            is_active=true,
                            failed_login_attempts=0,
                            locked_until=null,
                            updated_at=now()
                        where id=cast(:user_id as uuid)
                        """
                    ),
                    {
                        "email": target_email,
                        "display_name": target_display_name,
                        "user_id": str(current["id"]),
                    },
                )

        settings_value = dict(tenant.settings or {})
        settings_value["admin_email"] = target_email
        if password:
            settings_value["admin_password_ref"] = seal_secret(password)
        tenant.settings = settings_value
        await self.logs.record_platform_log(
            tenant_id=str(tenant.id),
            source="admin",
            service="control-plane",
            event="tenant_principal_admin_updated",
            message="Administrador principal do tenant atualizado pelo Control Plane.",
            actor=actor,
            details={
                "user_id": str(current["id"]),
                "email_changed": target_email != str(current["email"]).lower(),
                "password_rotated": bool(password),
                "sessions_revoked": bool(password),
            },
        )
        await self.session.commit()
        return await self.snapshot(tenant_id)
