import json
from secrets import token_urlsafe
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.security import hash_password


class PlatformAccessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def audit(self, actor_id: str | None, action: str, result: str = "SUCCESS", metadata: dict[str, Any] | None = None) -> None:
        await self.session.execute(
            text(
                """
                insert into platform_audit_logs(user_id, action, result, metadata)
                values(cast(:actor_id as uuid), :action, :result, cast(:metadata as jsonb))
                """
            ),
            {"actor_id": actor_id, "action": action, "result": result, "metadata": json.dumps(metadata or {}, ensure_ascii=False)},
        )

    async def list_permissions(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(text("select key, description, group_name from platform_permissions order by group_name, key"))).mappings().all()
        return [dict(row) for row in rows]

    async def list_roles(self) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    select r.id::text, r.name, r.description, r.is_system,
                           coalesce(array_agg(rp.permission_key order by rp.permission_key)
                                    filter(where rp.permission_key is not null), '{}') as permissions
                    from platform_roles r
                    left join platform_role_permissions rp on rp.role_id=r.id
                    group by r.id
                    order by r.name
                    """
                )
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    async def create_role(self, name: str, description: str | None, permissions: list[str], actor_id: str) -> dict[str, Any]:
        known = set((await self.session.execute(text("select key from platform_permissions where key = any(cast(:keys as text[]))"), {"keys": permissions or [""]})).scalars())
        unknown = sorted(set(permissions) - known)
        if unknown:
            raise APIError("IAM_PERMISSION_INVALID", "Permissões inválidas.", 400, {"permissions": unknown})
        try:
            role_id = (
                await self.session.execute(
                    text("insert into platform_roles(name, description) values(:name,:description) returning id::text"),
                    {"name": name.strip(), "description": description},
                )
            ).scalar_one()
        except Exception as exc:
            raise APIError("IAM_ROLE_EXISTS", "Já existe um perfil com este nome.", 409) from exc
        for permission in permissions:
            await self.session.execute(text("insert into platform_role_permissions(role_id, permission_key) values(cast(:id as uuid),:permission) on conflict do nothing"), {"id": role_id, "permission": permission})
        await self.audit(actor_id, "platform.role.create", metadata={"role_id": role_id, "name": name, "permissions": permissions})
        await self.session.commit()
        return next(item for item in await self.list_roles() if item["id"] == role_id)

    async def update_role(self, role_id: str, name: str, description: str | None, permissions: list[str], actor_id: str) -> dict[str, Any]:
        exists = (await self.session.execute(text("select is_system from platform_roles where id=cast(:id as uuid)"), {"id": role_id})).scalar_one_or_none()
        if exists is None:
            raise APIError("IAM_ROLE_NOT_FOUND", "Perfil não encontrado.", 404)
        await self.session.execute(text("update platform_roles set name=:name, description=:description, updated_at=now() where id=cast(:id as uuid)"), {"id": role_id, "name": name.strip(), "description": description})
        await self.session.execute(text("delete from platform_role_permissions where role_id=cast(:id as uuid)"), {"id": role_id})
        for permission in permissions:
            await self.session.execute(text("insert into platform_role_permissions(role_id, permission_key) select cast(:id as uuid), key from platform_permissions where key=:permission on conflict do nothing"), {"id": role_id, "permission": permission})
        await self.audit(actor_id, "platform.role.update", metadata={"role_id": role_id, "permissions": permissions})
        await self.session.commit()
        return next(item for item in await self.list_roles() if item["id"] == role_id)

    async def delete_role(self, role_id: str, actor_id: str) -> None:
        row = (await self.session.execute(text("select name, is_system from platform_roles where id=cast(:id as uuid)"), {"id": role_id})).mappings().first()
        if row is None:
            raise APIError("IAM_ROLE_NOT_FOUND", "Perfil não encontrado.", 404)
        if row["is_system"]:
            raise APIError("IAM_ROLE_SYSTEM", "Perfis de sistema não podem ser excluídos; edite as permissões.", 409)
        await self.session.execute(text("delete from platform_roles where id=cast(:id as uuid)"), {"id": role_id})
        await self.audit(actor_id, "platform.role.delete", metadata={"role_id": role_id, "name": row["name"]})
        await self.session.commit()

    async def list_users(self) -> list[dict[str, Any]]:
        rows = (
            await self.session.execute(
                text(
                    """
                    select u.id::text, u.email, coalesce(u.display_name, u.email) as display_name,
                           u.is_super_admin, u.is_active, u.must_change_password, u.created_at,
                           coalesce((select jsonb_agg(jsonb_build_object('id',r.id::text,'name',r.name) order by r.name)
                                     from platform_user_roles ur join platform_roles r on r.id=ur.role_id where ur.user_id=u.id),'[]'::jsonb) as roles,
                           coalesce((select jsonb_agg(jsonb_build_object('id',t.id::text,'name',t.name,'slug',t.slug) order by t.name)
                                     from platform_user_tenants ut join tenants t on t.id=ut.tenant_id where ut.user_id=u.id),'[]'::jsonb) as tenants
                    from platform_users u
                    order by u.created_at, u.email
                    """
                )
            )
        ).mappings().all()
        return [dict(row) for row in rows]

    async def create_user(self, email: str, display_name: str | None, password: str | None, role_ids: list[str], tenant_ids: list[str], actor_id: str) -> dict[str, Any]:
        initial_password = password or token_urlsafe(18)
        try:
            user_id = (
                await self.session.execute(
                    text("insert into platform_users(email,password_hash,display_name,is_super_admin,is_active,must_change_password) values(lower(:email),:password_hash,:display_name,false,true,:must_change) returning id::text"),
                    {"email": email, "password_hash": hash_password(initial_password), "display_name": display_name, "must_change": password is None},
                )
            ).scalar_one()
        except Exception as exc:
            raise APIError("IAM_USER_EXISTS", "Já existe usuário com este e-mail.", 409) from exc
        await self.set_user_access(user_id, role_ids, tenant_ids, actor_id, commit=False)
        await self.audit(actor_id, "platform.user.create", metadata={"user_id": user_id, "email": email, "roles": role_ids, "tenants": tenant_ids})
        await self.session.commit()
        user = next(item for item in await self.list_users() if item["id"] == user_id)
        user["initial_password"] = initial_password if password is None else None
        return user

    async def update_user(self, user_id: str, display_name: str | None, is_active: bool, role_ids: list[str], tenant_ids: list[str], actor_id: str) -> dict[str, Any]:
        if user_id == actor_id and not is_active:
            raise APIError("IAM_SELF_DISABLE", "Você não pode desativar sua própria conta.", 409)
        result = await self.session.execute(text("update platform_users set display_name=:display_name,is_active=:active,updated_at=now() where id=cast(:id as uuid)"), {"id": user_id, "display_name": display_name, "active": is_active})
        if result.rowcount == 0:
            raise APIError("IAM_USER_NOT_FOUND", "Usuário não encontrado.", 404)
        await self.set_user_access(user_id, role_ids, tenant_ids, actor_id, commit=False)
        if not is_active:
            await self.session.execute(text("update platform_user_sessions set revoked_at=coalesce(revoked_at,now()) where user_id=cast(:id as uuid)"), {"id": user_id})
        await self.audit(actor_id, "platform.user.update", metadata={"user_id": user_id, "active": is_active, "roles": role_ids, "tenants": tenant_ids})
        await self.session.commit()
        return next(item for item in await self.list_users() if item["id"] == user_id)

    async def set_user_access(self, user_id: str, role_ids: list[str], tenant_ids: list[str], actor_id: str, *, commit: bool = True) -> None:
        await self.session.execute(text("delete from platform_user_roles where user_id=cast(:id as uuid)"), {"id": user_id})
        await self.session.execute(text("delete from platform_user_tenants where user_id=cast(:id as uuid)"), {"id": user_id})
        for role_id in role_ids:
            await self.session.execute(text("insert into platform_user_roles(user_id,role_id) select cast(:uid as uuid),id from platform_roles where id=cast(:rid as uuid) on conflict do nothing"), {"uid": user_id, "rid": role_id})
        for tenant_id in tenant_ids:
            await self.session.execute(text("insert into platform_user_tenants(user_id,tenant_id) select cast(:uid as uuid),id from tenants where id=cast(:tid as uuid) on conflict do nothing"), {"uid": user_id, "tid": tenant_id})
        if commit:
            await self.audit(actor_id, "platform.user.access.update", metadata={"user_id": user_id, "roles": role_ids, "tenants": tenant_ids})
            await self.session.commit()

    async def reset_password(self, user_id: str, password: str | None, actor_id: str) -> dict[str, Any]:
        new_password = password or token_urlsafe(18)
        result = await self.session.execute(text("update platform_users set password_hash=:hash,must_change_password=:must_change,failed_login_attempts=0,locked_until=null,updated_at=now() where id=cast(:id as uuid)"), {"id": user_id, "hash": hash_password(new_password), "must_change": password is None})
        if result.rowcount == 0:
            raise APIError("IAM_USER_NOT_FOUND", "Usuário não encontrado.", 404)
        await self.session.execute(text("update platform_user_sessions set revoked_at=coalesce(revoked_at,now()) where user_id=cast(:id as uuid)"), {"id": user_id})
        await self.audit(actor_id, "platform.user.password.reset", metadata={"user_id": user_id})
        await self.session.commit()
        return {"user_id": user_id, "password": new_password, "must_change_password": password is None}

    async def delete_user(self, user_id: str, actor_id: str) -> None:
        if user_id == actor_id:
            raise APIError("IAM_SELF_DELETE", "Você não pode excluir sua própria conta.", 409)
        row = (await self.session.execute(text("select email,is_super_admin from platform_users where id=cast(:id as uuid)"), {"id": user_id})).mappings().first()
        if row is None:
            raise APIError("IAM_USER_NOT_FOUND", "Usuário não encontrado.", 404)
        if row["is_super_admin"]:
            count = int((await self.session.execute(text("select count(*) from platform_users where is_super_admin=true and is_active=true"))).scalar_one())
            if count <= 1:
                raise APIError("IAM_LAST_SUPER_ADMIN", "O último superadministrador não pode ser excluído.", 409)
        await self.session.execute(text("delete from platform_users where id=cast(:id as uuid)"), {"id": user_id})
        await self.audit(actor_id, "platform.user.delete", metadata={"user_id": user_id, "email": row["email"]})
        await self.session.commit()

    async def list_capabilities(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = (await self.session.execute(text("select capability_key as key, enabled, config, updated_at from tenant_capabilities where tenant_id=cast(:id as uuid) order by capability_key"), {"id": tenant_id})).mappings().all()
        return [dict(row) for row in rows]

    async def set_capability(self, tenant_id: str, key: str, enabled: bool, config: dict[str, Any], actor_id: str) -> dict[str, Any]:
        await self.session.execute(text("insert into tenant_capabilities(tenant_id,capability_key,enabled,config,updated_at) select id,:key,:enabled,cast(:config as jsonb),now() from tenants where id=cast(:id as uuid) on conflict(tenant_id,capability_key) do update set enabled=excluded.enabled,config=excluded.config,updated_at=now()"), {"id": tenant_id, "key": key, "enabled": enabled, "config": json.dumps(config, ensure_ascii=False)})
        await self.audit(actor_id, "tenant.capability.update", metadata={"tenant_id": tenant_id, "capability": key, "enabled": enabled})
        await self.session.commit()
        row = (await self.session.execute(text("select capability_key as key,enabled,config,updated_at from tenant_capabilities where tenant_id=cast(:id as uuid) and capability_key=:key"), {"id": tenant_id, "key": key})).mappings().one()
        return dict(row)
