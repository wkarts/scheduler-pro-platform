"""Persisted tenant-local IAM; delegation checked again under a transaction lock."""

import asyncio
import json
import secrets
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.security import AuthPrincipal, hash_opaque_token, hash_password, verify_password
from app.core.tenant_context import TenantContext
from app.services.tenant_mail_service import TenantMailService

# This lock is scoped by PostgreSQL database, not globally across all customers.
LOCK_SQL = text("select pg_advisory_xact_lock(739148201)")
PERMISSIONS_SQL = """select distinct p.key from permissions p
    join role_permissions rp on rp.permission_id=p.id
    join roles r on r.id=rp.role_id and r.is_active
    join user_roles ur on ur.role_id=r.id where ur.user_id=cast(:id as uuid)"""
USER_COLUMNS = """u.id::text,u.display_name,u.email,u.phone,u.is_active,u.verification_required,
    u.email_verified_at,u.last_login_at,u.created_at,u.professional_id::text,
    p.name as professional_name,(u.avatar_key is not null) as has_avatar"""


async def permissions_for(
    session: AsyncSession, user_id: str, *, include_inactive: bool = False
) -> set[str]:
    query = PERMISSIONS_SQL.replace(" and r.is_active", "") if include_inactive else PERMISSIONS_SQL
    return {str(p) for p in (await session.execute(text(query), {"id": user_id})).scalars()}


def ensure_delegation(granted: set[str], allowed: set[str]) -> None:
    if not granted.issubset(allowed):
        raise APIError(
            "IAM_DELEGATION_DENIED", "Você não pode gerenciar privilégios superiores aos seus.", 403
        )


def validate_password(value: str) -> None:
    if not settings.password_reset_min_length <= len(value) <= 512:
        raise APIError(
            "PASSWORD_TOO_SHORT",
            f"Use de {settings.password_reset_min_length} a 512 caracteres.",
            422,
        )


async def revoke_access(session: AsyncSession, user_id: str, *, email_tokens: bool = True) -> None:
    for table in ("user_sessions", "refresh_tokens"):
        await session.execute(
            text(
                f"update {table} set revoked_at=coalesce(revoked_at,now()) where user_id=cast(:id as uuid)"
            ),
            {"id": user_id},
        )
    await session.execute(
        text(
            "update service_api_tokens set revoked_at=coalesce(revoked_at,now()) where owner_id=cast(:id as uuid)"
        ),
        {"id": user_id},
    )
    await session.execute(
        text(
            "update password_reset_tokens set used_at=coalesce(used_at,now()) where user_id=cast(:id as uuid)"
        ),
        {"id": user_id},
    )
    if email_tokens:
        await session.execute(
            text(
                "update identity_email_tokens set used_at=coalesce(used_at,now()) where user_id=cast(:id as uuid)"
            ),
            {"id": user_id},
        )


class IdentityService:
    def __init__(
        self, session: AsyncSession, context: TenantContext, actor: AuthPrincipal | None = None
    ) -> None:
        self.session, self.context, self.actor = session, context, actor

    async def audit(self, action: str, metadata: dict[str, Any]) -> None:
        await self.session.execute(
            text("""insert into audit_logs(user_id,action,result,metadata)
            values(cast(:actor as uuid),:action,'SUCCESS',cast(:metadata as jsonb))"""),
            {
                "actor": self.actor.user_id if self.actor else None,
                "action": action,
                "metadata": json.dumps(metadata),
            },
        )

    async def authorize(self, permission: str | None = None, *, lock: bool = False) -> set[str]:
        if lock:
            await self.session.execute(LOCK_SQL)
        if (
            self.actor is None
            or self.actor.user_type != "tenant"
            or self.actor.tenant_id != self.context.tenant_id
        ):
            raise APIError("AUTH_SCOPE_INVALID", "Acesso restrito à empresa autenticada.", 403)
        # Do not trust a principal constructed before a concurrent permission/session change.
        active = await self.session.scalar(
            text("""select 1 from users u join user_sessions s on s.user_id=u.id
            where u.id=cast(:id as uuid) and s.id=cast(:sid as uuid) and u.is_active
            and (not u.verification_required or u.email_verified_at is not null)
            and s.revoked_at is null and s.expires_at>now()
            and (not u.two_factor_enabled or s.second_factor_verified)"""),
            {"id": self.actor.user_id, "sid": self.actor.session_id},
        )
        if active is None:
            raise APIError("AUTH_SESSION_INVALID", "Sessão inválida ou expirada.", 401)
        allowed = await permissions_for(self.session, self.actor.user_id)
        if permission and permission not in allowed:
            raise APIError("IAM_PERMISSION_DENIED", "Sem permissão para esta ação.", 403)
        return allowed

    async def catalog(self) -> dict[str, Any]:
        allowed = await self.authorize()
        rows = (
            await self.session.execute(text("select key,description from permissions order by key"))
        ).mappings()
        return {
            "actor_id": self.actor.user_id if self.actor else None,
            "actor_permissions": sorted(allowed),
            "permissions": [dict(row, delegable=row["key"] in allowed) for row in rows],
            "password_min_length": settings.password_reset_min_length,
        }

    async def groups(self) -> list[dict[str, Any]]:
        allowed = await self.authorize()
        if not {"users.read", "groups.manage"} & allowed:
            raise APIError("IAM_PERMISSION_DENIED", "Sem permissão para consultar grupos.", 403)
        return [
            dict(r)
            for r in (
                await self.session.execute(
                    text("""select r.id::text,r.name,
            coalesce(r.description,'') as description,r.is_active,
            (select count(*) from user_roles ur where ur.role_id=r.id) as member_count,
            coalesce((select jsonb_agg(p.key order by p.key) from permissions p
            join role_permissions rp on rp.permission_id=p.id where rp.role_id=r.id),'[]') as permissions
            from roles r order by r.name""")
                )
            ).mappings()
        ]

    async def _user(self, user_id: str) -> dict[str, Any]:
        row = (
            (
                await self.session.execute(
                    text(
                        f"select {USER_COLUMNS} from users u left join professionals p on p.id=u.professional_id where u.id=cast(:id as uuid)"
                    ),
                    {"id": user_id},
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise APIError("IAM_USER_NOT_FOUND", "Usuário não encontrado nesta empresa.", 404)
        result = dict(row)
        result["groups"] = [
            dict(g)
            for g in (
                await self.session.execute(
                    text(
                        "select r.id::text,r.name,r.is_active from roles r join user_roles ur on ur.role_id=r.id where ur.user_id=cast(:id as uuid) order by r.name"
                    ),
                    {"id": user_id},
                )
            ).mappings()
        ]
        result["permissions"] = sorted(await permissions_for(self.session, user_id))
        return result

    async def user(self, user_id: str) -> dict[str, Any]:
        await self.authorize("users.read")
        return await self._user(user_id)

    async def profile(self) -> dict[str, Any]:
        await self.authorize()
        assert self.actor
        return await self._user(self.actor.user_id)

    async def users(self, query: str, offset: int) -> dict[str, Any]:
        await self.authorize("users.read")
        params = {"q": f"%{query}%", "offset": offset}
        where = "where u.display_name ilike :q or u.email ilike :q"
        count = await self.session.scalar(text(f"select count(*) from users u {where}"), params)
        rows = (
            await self.session.execute(
                text(
                    f"select u.id::text from users u {where} order by u.display_name,u.id limit 25 offset :offset"
                ),
                params,
            )
        ).scalars()
        return {"items": [await self._user(str(i)) for i in rows], "total": count}

    async def _target(self, user_id: str, allowed: set[str]) -> dict[str, Any]:
        assert self.actor
        if user_id == self.actor.user_id:
            raise APIError(
                "IAM_SELF_MANAGEMENT_DENIED",
                "Use Meu perfil; não altere seus próprios grupos ou estado.",
                403,
            )
        user = await self._user(user_id)
        ensure_delegation(
            await permissions_for(self.session, user_id, include_inactive=True), allowed
        )
        return user

    async def _groups_allowed(self, group_ids: list[str], allowed: set[str]) -> None:
        for group_id in set(group_ids):
            exists = await self.session.scalar(
                text("select id from roles where id=cast(:id as uuid)"), {"id": group_id}
            )
            if not exists:
                raise APIError("IAM_GROUP_NOT_FOUND", "Grupo não encontrado nesta empresa.", 404)
            permissions = set(
                (
                    await self.session.execute(
                        text(
                            "select p.key from permissions p join role_permissions rp on rp.permission_id=p.id where rp.role_id=cast(:id as uuid)"
                        ),
                        {"id": group_id},
                    )
                ).scalars()
            )
            ensure_delegation(permissions, allowed)

    async def _professional(self, value: str | None, user_id: str) -> None:
        if not value:
            return
        row = await self.session.scalar(
            text("select id from professionals where id=cast(:id as uuid) for update"),
            {"id": value},
        )
        if row is None:
            raise APIError(
                "IAM_PROFESSIONAL_NOT_FOUND", "Profissional não encontrado nesta empresa.", 404
            )
        used = await self.session.scalar(
            text(
                "select id from users where professional_id=cast(:id as uuid) and id<>cast(:uid as uuid)"
            ),
            {"id": value, "uid": user_id},
        )
        if used:
            raise APIError(
                "IAM_PROFESSIONAL_IN_USE", "Profissional já vinculado a outra conta.", 409
            )

    async def _unique_email(self, email: str, user_id: str) -> None:
        other = await self.session.scalar(
            text("select id from users where lower(email)=:email and id<>cast(:id as uuid)"),
            {"email": email.lower(), "id": user_id},
        )
        if other:
            raise APIError("IAM_EMAIL_IN_USE", "E-mail indisponível nesta empresa.", 409)

    async def _assign_groups(self, user_id: str, ids: list[str]) -> None:
        await self.session.execute(
            text("delete from user_roles where user_id=cast(:id as uuid)"), {"id": user_id}
        )
        for group_id in set(ids):
            await self.session.execute(
                text(
                    "insert into user_roles(user_id,role_id) values(cast(:id as uuid),cast(:group as uuid))"
                ),
                {"id": user_id, "group": group_id},
            )

    async def _last_admin(self) -> None:
        count = await self.session.scalar(
            text("""select count(distinct u.id) from users u
            join user_roles ur on ur.user_id=u.id join roles r on r.id=ur.role_id and r.is_active
            join role_permissions rp on rp.role_id=r.id join permissions p on p.id=rp.permission_id
            where u.is_active and (not u.verification_required or u.email_verified_at is not null)
            group by u.id having bool_or(p.key='tenant.manage') and bool_or(p.key='users.manage') and bool_or(p.key='groups.manage') limit 1""")
        )
        if not count:
            raise APIError(
                "IAM_LAST_ADMIN", "Mantenha ao menos um administrador ativo da empresa.", 409
            )

    async def create_user(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed = await self.authorize("users.manage", lock=True)
        uid, email = str(uuid4()), str(data["email"]).strip().lower()
        await self._unique_email(email, uid)
        await self._groups_allowed(data["group_ids"], allowed)
        await self._professional(data["professional_id"], uid)
        await self.session.execute(
            text("""insert into users(id,email,display_name,phone,professional_id,password_hash,verification_required)
            values(cast(:id as uuid),:email,:display_name,:phone,cast(:professional_id as uuid),:password_hash,true)"""),
            {
                **data,
                "id": uid,
                "email": email,
                "password_hash": await asyncio.to_thread(hash_password, secrets.token_urlsafe(48)),
            },
        )
        await self._assign_groups(uid, data["group_ids"])
        await self.audit(
            "iam.user.created",
            {
                "target_user_id": uid,
                "groups": data["group_ids"],
                "professional_id": data["professional_id"],
            },
        )
        sent = await self._issue_email(uid, "invite", email, cooldown=False)
        result = await self._user(uid)
        result["invitation_sent"] = sent
        return result

    async def update_user(self, uid: str, data: dict[str, Any]) -> dict[str, Any]:
        allowed = await self.authorize("users.manage", lock=True)
        old = await self._target(uid, allowed)
        await self._groups_allowed(data["group_ids"], allowed)
        await self._professional(data["professional_id"], uid)
        await self.session.execute(
            text(
                "update users set display_name=:display_name,phone=:phone,professional_id=cast(:professional_id as uuid),is_active=:is_active,updated_at=now() where id=cast(:id as uuid)"
            ),
            {**data, "id": uid},
        )
        await self._assign_groups(uid, data["group_ids"])
        await self._last_admin()
        if not data["is_active"] or {g["id"] for g in old["groups"]} != set(data["group_ids"]):
            await revoke_access(self.session, uid, email_tokens=not data["is_active"])
        await self.audit(
            "iam.user.updated",
            {
                "target_user_id": uid,
                "is_active": data["is_active"],
                "groups": data["group_ids"],
                "professional_id": data["professional_id"],
            },
        )
        await self.session.commit()
        return await self._user(uid)

    async def save_group(self, group_id: str | None, data: dict[str, Any]) -> dict[str, Any]:
        allowed = await self.authorize("groups.manage", lock=True)
        grant = set(data["permissions"])
        known = set((await self.session.execute(text("select key from permissions"))).scalars())
        if grant - known:
            raise APIError("IAM_PERMISSION_UNKNOWN", "Permissão desconhecida.", 422)
        ensure_delegation(grant, allowed)
        gid = group_id or str(uuid4())
        other = await self.session.scalar(
            text("select id from roles where lower(name)=lower(:name) and id<>cast(:id as uuid)"),
            {"name": data["name"], "id": gid},
        )
        if other:
            raise APIError("IAM_GROUP_NAME_IN_USE", "Nome de grupo já utilizado.", 409)
        if group_id:
            if not await self.session.scalar(
                text("select id from roles where id=cast(:id as uuid)"), {"id": gid}
            ):
                raise APIError("IAM_GROUP_NOT_FOUND", "Grupo não encontrado.", 404)
            await self._groups_allowed([gid], allowed)
            members = list(
                (
                    await self.session.execute(
                        text(
                            "select user_id::text from user_roles where role_id=cast(:id as uuid)"
                        ),
                        {"id": gid},
                    )
                ).scalars()
            )
            for member in members:
                ensure_delegation(
                    await permissions_for(self.session, member, include_inactive=True), allowed
                )
            await self.session.execute(
                text(
                    "update roles set name=:name,description=:description,is_active=:is_active where id=cast(:id as uuid)"
                ),
                {**data, "id": gid},
            )
            await self.session.execute(
                text("delete from role_permissions where role_id=cast(:id as uuid)"), {"id": gid}
            )
        else:
            await self.session.execute(
                text(
                    "insert into roles(id,name,description,is_active) values(cast(:id as uuid),:name,:description,:is_active)"
                ),
                {**data, "id": gid},
            )
        for key in sorted(grant):
            await self.session.execute(
                text(
                    "insert into role_permissions(role_id,permission_id) select cast(:id as uuid),id from permissions where key=:key"
                ),
                {"id": gid, "key": key},
            )
        await self._last_admin()
        await self.audit(
            "iam.group.updated" if group_id else "iam.group.created",
            {"group_id": gid, "permissions": sorted(grant), "is_active": data["is_active"]},
        )
        await self.session.commit()
        return {"id": gid}

    async def update_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.authorize(lock=True)
        assert self.actor
        await self.session.execute(
            text(
                "update users set display_name=:display_name,phone=:phone,updated_at=now() where id=cast(:id as uuid)"
            ),
            {**data, "id": self.actor.user_id},
        )
        await self.audit("iam.profile.updated", {"target_user_id": self.actor.user_id})
        await self.session.commit()
        return await self._user(self.actor.user_id)

    async def _check_password(self, password: str) -> None:
        assert self.actor
        row = (
            (
                await self.session.execute(
                    text(
                        "select password_hash,failed_login_attempts,locked_until>now() as locked from users where id=cast(:id as uuid) for update"
                    ),
                    {"id": self.actor.user_id},
                )
            )
            .mappings()
            .one()
        )
        if row["locked"]:
            raise APIError("AUTH_REAUTH_LOCKED", "Aguarde antes de tentar novamente.", 429)
        if not await asyncio.to_thread(verify_password, password, row["password_hash"]):
            attempts = int(row["failed_login_attempts"]) + 1
            await self.session.execute(
                text(
                    "update users set failed_login_attempts=:attempts,locked_until=case when :attempts>=:maximum then now()+make_interval(mins=>:minutes) else locked_until end where id=cast(:id as uuid)"
                ),
                {
                    "id": self.actor.user_id,
                    "attempts": attempts,
                    "maximum": settings.max_login_attempts,
                    "minutes": settings.login_lock_minutes,
                },
            )
            await self.session.commit()
            raise APIError("AUTH_PASSWORD_INVALID", "Senha atual inválida.", 403)

    async def change_password(self, current: str, new: str) -> None:
        await self.authorize(lock=True)
        await self._check_password(current)
        validate_password(new)
        assert self.actor
        await self.session.execute(
            text(
                "update users set password_hash=:hash,failed_login_attempts=0,locked_until=null,updated_at=now() where id=cast(:id as uuid)"
            ),
            {"id": self.actor.user_id, "hash": await asyncio.to_thread(hash_password, new)},
        )
        await revoke_access(self.session, self.actor.user_id)
        await self.audit("iam.password.changed", {"target_user_id": self.actor.user_id})
        await self.session.commit()

    async def invite(self, uid: str) -> bool:
        allowed = await self.authorize("users.manage", lock=True)
        user = await self._target(uid, allowed)
        if not user["is_active"]:
            raise APIError("IAM_USER_INACTIVE", "Ative a conta antes de enviar o convite.", 409)
        return await self._issue_email(
            uid,
            "invite"
            if user["verification_required"] and not user["email_verified_at"]
            else "verify",
            user["email"],
        )

    async def request_email(self, email: str | None = None, password: str | None = None) -> bool:
        await self.authorize(lock=True)
        assert self.actor
        if email is not None:
            await self._check_password(password or "")
            email = email.strip().lower()
            await self._unique_email(email, self.actor.user_id)
        user = await self._user(self.actor.user_id)
        return await self._issue_email(
            self.actor.user_id, "change" if email else "verify", email or user["email"]
        )

    async def _issue_email(
        self, uid: str, purpose: str, email: str, *, cooldown: bool = True
    ) -> bool:
        if cooldown and await self.session.scalar(
            text(
                "select 1 from identity_email_tokens where user_id=cast(:id as uuid) and created_at>now()-interval '60 seconds' limit 1"
            ),
            {"id": uid},
        ):
            raise APIError("IAM_EMAIL_COOLDOWN", "Aguarde um minuto antes de reenviar.", 429)
        raw = secrets.token_urlsafe(48)
        await self.session.execute(
            text(
                "update identity_email_tokens set used_at=coalesce(used_at,now()) where user_id=cast(:id as uuid)"
            ),
            {"id": uid},
        )
        await self.session.execute(
            text("""insert into identity_email_tokens(user_id,token_hash,purpose,previous_email,email,expires_at)
            select id,:hash,:purpose,email,:email,now()+interval '24 hours' from users where id=cast(:id as uuid)"""),
            {"id": uid, "hash": hash_opaque_token(raw), "purpose": purpose, "email": email},
        )
        mail = TenantMailService(self.session)
        # Resolve existing mail configuration then release DB connection before SMTP.
        smtp = await mail.config()
        if await mail._delivery_mode() == "platform":
            row = await mail._row()
            smtp = mail._platform_config() if row and row["enabled"] else None
        await self.audit("iam.email.requested", {"target_user_id": uid, "purpose": purpose})
        await self.session.commit()
        if smtp is None:
            return False
        link = f"https://{self.context.hostname}/#verificar-email?token={raw}"
        message = f"Confirme seu acesso ao Scheduler Pro:\n\n{link}\n\nLink válido por 24 horas e de uso único. Se não solicitou, ignore esta mensagem."
        try:
            await asyncio.to_thread(
                TenantMailService._send_sync,
                smtp,
                email,
                "Scheduler Pro — confirmar acesso",
                message,
            )
        except Exception:
            return False
        return True

    async def confirm(self, raw: str, password: str | None) -> None:
        await self.session.execute(LOCK_SQL)
        row = (
            (
                await self.session.execute(
                    text("""select t.id::text,t.user_id::text,t.purpose,t.email,t.previous_email,
            t.expires_at>now() as valid,t.used_at,u.is_active,u.email as current_email
            from identity_email_tokens t join users u on u.id=t.user_id where t.token_hash=:hash for update of t,u"""),
                    {"hash": hash_opaque_token(raw)},
                )
            )
            .mappings()
            .first()
        )
        if (
            not row
            or not row["valid"]
            or row["used_at"]
            or not row["is_active"]
            or row["previous_email"] != row["current_email"]
        ):
            raise APIError("IAM_EMAIL_TOKEN_INVALID", "Link inválido, utilizado ou expirado.", 400)
        uid = row["user_id"]
        await self._unique_email(row["email"], uid)
        if row["purpose"] == "invite":
            if not password:
                raise APIError(
                    "IAM_PASSWORD_REQUIRED", "Defina sua senha para aceitar o convite.", 422
                )
            validate_password(password)
            await self.session.execute(
                text("update users set password_hash=:hash where id=cast(:id as uuid)"),
                {"id": uid, "hash": await asyncio.to_thread(hash_password, password)},
            )
        await self.session.execute(
            text(
                "update users set email=:email,email_verified_at=now(),verification_required=false,updated_at=now() where id=cast(:id as uuid)"
            ),
            {"id": uid, "email": row["email"]},
        )
        await revoke_access(self.session, uid)
        await self.audit("iam.email.confirmed", {"target_user_id": uid, "purpose": row["purpose"]})
        await self.session.commit()
