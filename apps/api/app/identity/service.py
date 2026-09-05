"""Tenant-scoped identity administration over the existing users/roles/auth tables."""

import asyncio
from datetime import UTC, datetime, timedelta
import json
import logging
import secrets
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.security import AuthPrincipal, hash_opaque_token, hash_password, verify_password
from app.core.tenant_context import TenantContext
from app.identity.policy import assert_delegable, lock_identity, permission_keys, revoke_access
from app.services.mail_service import mail_delivery
from app.services.phone_normalization import PhoneNormalizationService
from app.services.tenant_mail_service import TenantMailService

logger = logging.getLogger(__name__)
USER_SELECT = """
    select u.id::text,u.display_name,u.email,u.phone,u.is_active,u.verification_required,
           u.email_verified_at,u.last_login_at,u.created_at,u.professional_id::text,
           p.name as professional_name,(u.avatar_key is not null) as has_avatar,
           coalesce((select jsonb_agg(jsonb_build_object('id',r.id::text,'name',r.name,
               'is_active',r.is_active) order by r.name) from roles r
               join user_roles ur on ur.role_id=r.id where ur.user_id=u.id),'[]'::jsonb) as groups
    from users u left join professionals p on p.id=u.professional_id
"""
GROUP_SELECT = """
    select r.id::text,r.name,coalesce(r.description,'') as description,r.is_active,
      (select count(*) from user_roles ur where ur.role_id=r.id) as member_count,
      coalesce((select jsonb_agg(p.key order by p.key) from role_permissions rp
      join permissions p on p.id=rp.permission_id where rp.role_id=r.id),'[]'::jsonb) as permissions
    from roles r
"""


def _pattern(value: str) -> str:
    return (
        "%"
        + value.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        + "%"
    )


class TenantIdentityService:
    def __init__(
        self, session: AsyncSession, context: TenantContext, actor: AuthPrincipal | None = None
    ) -> None:
        self.session = session
        self.context = context
        self.actor = actor
        self.authority: set[str] = set()
        self.admins_before = 0

    async def _admin_count(self) -> int:
        return int(
            await self.session.scalar(
                text("""
            select count(*) from users u where u.is_active
            and (not u.verification_required or u.email_verified_at is not null)
            and exists(select 1 from user_roles ur join roles r on r.id=ur.role_id and r.is_active
              join role_permissions rp on rp.role_id=r.id join permissions p on p.id=rp.permission_id
              where ur.user_id=u.id and p.key='users.manage')
            and exists(select 1 from user_roles ur join roles r on r.id=ur.role_id and r.is_active
              join role_permissions rp on rp.role_id=r.id join permissions p on p.id=rp.permission_id
              where ur.user_id=u.id and p.key='groups.manage')
        """)
            )
            or 0
        )

    async def begin(self, required: str | None = None) -> None:
        if (
            self.actor is None
            or self.actor.user_type != "tenant"
            or self.actor.tenant_id != self.context.tenant_id
        ):
            raise APIError("IAM_SCOPE_DENIED", "Conta de acesso inválida para esta empresa.", 403)
        await lock_identity(self.session)
        valid = await self.session.scalar(
            text("""
            select exists(select 1 from users u join user_sessions s on s.user_id=u.id
            where u.id=cast(:id as uuid) and s.id=cast(:sid as uuid) and u.is_active
            and (not u.verification_required or u.email_verified_at is not null)
            and s.revoked_at is null and s.expires_at>now()
            and (not u.two_factor_enabled or s.second_factor_verified))
        """),
            {"id": self.actor.user_id, "sid": self.actor.session_id},
        )
        if not valid:
            raise APIError("AUTH_SESSION_INVALID", "Sessão inválida ou expirada.", 401)
        self.authority = await permission_keys(self.session, self.actor.user_id)
        if required is not None and required not in self.authority:
            raise APIError("AUTH_PERMISSION_DENIED", "Permissão insuficiente.", 403)
        self.admins_before = await self._admin_count()

    async def audit(self, action: str, metadata: dict[str, Any], result: str = "SUCCESS") -> None:
        await self.session.execute(
            text("""
            insert into audit_logs(user_id,action,result,metadata)
            values(cast(:actor as uuid),:action,:result,cast(:metadata as jsonb))
        """),
            {
                "actor": self.actor.user_id if self.actor else None,
                "action": action,
                "result": result,
                "metadata": json.dumps(metadata, default=str),
            },
        )

    async def finish(self, action: str, metadata: dict[str, Any]) -> None:
        if self.admins_before > 0 and await self._admin_count() == 0:
            await self.session.rollback()
            raise APIError(
                "IAM_LAST_ADMIN",
                "Mantenha pelo menos um administrador ativo e apto a gerenciar usuários e grupos.",
                409,
            )
        await self.audit(action, metadata)
        await self.session.commit()

    async def user(self, user_id: str) -> dict[str, Any]:
        row = (
            (
                await self.session.execute(
                    text(USER_SELECT + " where u.id=cast(:id as uuid)"), {"id": user_id}
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise APIError("IAM_USER_NOT_FOUND", "Usuário não encontrado nesta empresa.", 404)
        value = dict(row)
        value["permissions"] = sorted(await permission_keys(self.session, user_id))
        return value

    async def list_users(self, q: str = "", offset: int = 0) -> dict[str, Any]:
        where = " where (lower(u.email) like :q or lower(u.display_name) like :q)"
        params = {"q": _pattern(q), "offset": offset}
        rows = await self.session.execute(
            text(
                USER_SELECT + where + " order by lower(u.display_name),u.id limit 25 offset :offset"
            ),
            params,
        )
        total = await self.session.scalar(text("select count(*) from users u" + where), params)
        return {"items": [dict(row) for row in rows.mappings()], "total": total}

    async def groups(self) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in (
                await self.session.execute(text(GROUP_SELECT + " order by lower(r.name),r.id"))
            ).mappings()
        ]

    async def catalog(self) -> dict[str, Any]:
        assert self.actor is not None
        keys = await permission_keys(self.session, self.actor.user_id)
        rows = (
            await self.session.execute(
                text(
                    "select key,coalesce(description,key) as description from permissions order by key"
                )
            )
        ).mappings()
        return {
            "actor_id": self.actor.user_id,
            "actor_permissions": sorted(keys),
            "password_min_length": settings.password_reset_min_length,
            "permissions": [{**dict(row), "delegable": row["key"] in keys} for row in rows],
        }

    async def target(self, user_id: str, *, allow_self: bool = False) -> dict[str, Any]:
        if self.actor and user_id == self.actor.user_id and not allow_self:
            raise APIError(
                "IAM_SELF_ADMINISTRATION",
                "Use Meu perfil para seus dados. Outro administrador deve alterar seus grupos ou situação.",
                409,
            )
        value = await self.user(user_id)
        # Dormant group permissions count too: cannot launder grants by disabling a group first.
        assert_delegable(
            await permission_keys(self.session, user_id, include_inactive=True), self.authority
        )
        return value

    async def _groups_for_assignment(self, ids: list[str]) -> None:
        if not ids:
            return
        rows = (
            (
                await self.session.execute(
                    text(GROUP_SELECT + " where r.id=any(cast(:ids as uuid[]))"), {"ids": ids}
                )
            )
            .mappings()
            .all()
        )
        if len(rows) != len(set(ids)):
            raise APIError("IAM_GROUP_NOT_FOUND", "Grupo não encontrado nesta empresa.", 422)
        for row in rows:
            assert_delegable(set(row["permissions"]), self.authority)

    async def _professional(self, professional_id: str | None, user_id: str | None = None) -> None:
        if professional_id is None:
            return
        exists = await self.session.scalar(
            text("select id from professionals where id=cast(:id as uuid)"), {"id": professional_id}
        )
        if not exists:
            raise APIError(
                "IAM_PROFESSIONAL_NOT_FOUND", "Profissional não encontrado nesta empresa.", 422
            )
        linked = await self.session.scalar(
            text("select id::text from users where professional_id=cast(:id as uuid)"),
            {"id": professional_id},
        )
        if linked and linked != user_id:
            raise APIError(
                "IAM_PROFESSIONAL_LINKED", "Este profissional já está vinculado a outra conta.", 409
            )

    async def _email_available(self, email: str, user_id: str | None = None) -> None:
        exists = await self.session.scalar(
            text(
                "select id::text from users where lower(email)=:email and (cast(:id as text) is null or id::text<>:id) limit 1"
            ),
            {"email": email.lower(), "id": user_id},
        )
        if exists:
            raise APIError("IAM_EMAIL_EXISTS", "Este e-mail já está cadastrado nesta empresa.", 409)

    async def create_user(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.begin("users.manage")
        await self._email_available(data["email"])
        ids = list(dict.fromkeys(data["group_ids"]))
        await self._groups_for_assignment(ids)
        await self._professional(data["professional_id"])
        phone = (await PhoneNormalizationService.from_session(self.session)).normalize(
            data.get("phone")
        )
        user_id = str(uuid4())
        await self.session.execute(
            text("""
            insert into users(id,email,password_hash,display_name,phone,professional_id,verification_required)
            values(cast(:id as uuid),:email,:password,:name,:phone,cast(:professional as uuid),true)
        """),
            {
                "id": user_id,
                "email": data["email"].lower(),
                "password": hash_password(secrets.token_urlsafe(48)),
                "name": data["display_name"],
                "phone": phone,
                "professional": data["professional_id"],
            },
        )
        await self._assign(user_id, ids)
        await self.finish(
            "iam.user.created",
            {
                "target_user_id": user_id,
                "group_ids": ids,
                "professional_id": data["professional_id"],
            },
        )
        sent = await self.invite(user_id)
        return {**await self.user(user_id), "invitation_sent": sent}

    async def _assign(self, user_id: str, group_ids: list[str]) -> None:
        await self.session.execute(
            text("delete from user_roles where user_id=cast(:id as uuid)"), {"id": user_id}
        )
        for group in group_ids:
            await self.session.execute(
                text(
                    "insert into user_roles(user_id,role_id) values(cast(:id as uuid),cast(:group as uuid))"
                ),
                {"id": user_id, "group": group},
            )

    async def update_user(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        await self.begin("users.manage")
        before = await self.target(user_id)
        ids = list(dict.fromkeys(data["group_ids"]))
        await self._groups_for_assignment(ids)
        await self._professional(data["professional_id"], user_id)
        phone = (await PhoneNormalizationService.from_session(self.session)).normalize(
            data.get("phone")
        )
        await self.session.execute(
            text("""
            update users set display_name=:name,phone=:phone,is_active=:active,
            professional_id=cast(:professional as uuid),updated_at=now() where id=cast(:id as uuid)
        """),
            {
                "id": user_id,
                "name": data["display_name"],
                "phone": phone,
                "active": data["is_active"],
                "professional": data["professional_id"],
            },
        )
        await self._assign(user_id, ids)
        if not data["is_active"]:
            await revoke_access(self.session, user_id)
        await self.finish(
            "iam.user.updated",
            {
                "target_user_id": user_id,
                "before": {
                    "is_active": before["is_active"],
                    "group_ids": [g["id"] for g in before["groups"]],
                    "professional_id": before["professional_id"],
                },
                "after": {
                    "is_active": data["is_active"],
                    "group_ids": ids,
                    "professional_id": data["professional_id"],
                },
            },
        )
        return await self.user(user_id)

    async def save_group(self, data: dict[str, Any], group_id: str | None = None) -> dict[str, Any]:
        await self.begin("groups.manage")
        before: dict[str, Any] | None = None
        if group_id:
            row = (
                (
                    await self.session.execute(
                        text(GROUP_SELECT + " where r.id=cast(:id as uuid)"), {"id": group_id}
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("IAM_GROUP_NOT_FOUND", "Grupo não encontrado.", 404)
            before = dict(row)
            assert_delegable(set(row["permissions"]), self.authority)
        grants = set(data["permissions"])
        assert_delegable(grants, self.authority)
        duplicate = await self.session.scalar(
            text(
                "select id::text from roles where lower(name)=lower(:name) and (cast(:id as text) is null or id::text<>:id) limit 1"
            ),
            {"name": data["name"], "id": group_id},
        )
        if duplicate:
            raise APIError("IAM_GROUP_EXISTS", "Já existe um grupo com este nome.", 409)
        if group_id is None:
            group_id = str(uuid4())
            await self.session.execute(
                text(
                    "insert into roles(id,name,description,is_active) values(cast(:id as uuid),:name,:description,:is_active)"
                ),
                {"id": group_id, **data},
            )
        else:
            await self.session.execute(
                text(
                    "update roles set name=:name,description=:description,is_active=:is_active,updated_at=now() where id=cast(:id as uuid)"
                ),
                {"id": group_id, **data},
            )
        await self.session.execute(
            text("delete from role_permissions where role_id=cast(:id as uuid)"), {"id": group_id}
        )
        await self.session.execute(
            text(
                "insert into role_permissions(role_id,permission_id) select cast(:id as uuid),id from permissions where key=any(cast(:keys as text[]))"
            ),
            {"id": group_id, "keys": sorted(grants)},
        )
        await self.finish(
            "iam.group.updated" if before else "iam.group.created",
            {"group_id": group_id, "before": before, "after": data},
        )
        return dict(
            (
                await self.session.execute(
                    text(GROUP_SELECT + " where r.id=cast(:id as uuid)"), {"id": group_id}
                )
            )
            .mappings()
            .one()
        )

    async def revoke_user(self, user_id: str) -> None:
        await self.begin("users.manage")
        await self.target(user_id)
        await revoke_access(self.session, user_id)
        await self.finish("iam.user.access_revoked", {"target_user_id": user_id})

    async def update_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        await self.begin()
        assert self.actor is not None
        phone = (await PhoneNormalizationService.from_session(self.session)).normalize(
            data.get("phone")
        )
        await self.session.execute(
            text(
                "update users set display_name=:name,phone=:phone,updated_at=now() where id=cast(:id as uuid)"
            ),
            {"id": self.actor.user_id, "name": data["display_name"], "phone": phone},
        )
        await self.finish("iam.profile.updated", {"target_user_id": self.actor.user_id})
        return await self.user(self.actor.user_id)

    async def _check_password(self, password: str) -> None:
        assert self.actor is not None
        row = (
            (
                await self.session.execute(
                    text(
                        "select password_hash,locked_until,failed_login_attempts from users where id=cast(:id as uuid)"
                    ),
                    {"id": self.actor.user_id},
                )
            )
            .mappings()
            .one()
        )
        if row["locked_until"] and row["locked_until"] > datetime.now(UTC):
            raise APIError(
                "IAM_PASSWORD_LOCKED", "Aguarde antes de tentar confirmar sua senha novamente.", 429
            )
        if not verify_password(password, row["password_hash"]):
            attempts = int(row["failed_login_attempts"] or 0) + 1
            locked_until = (
                datetime.now(UTC) + timedelta(minutes=settings.login_lock_minutes)
                if attempts >= settings.max_login_attempts
                else None
            )
            await self.session.execute(
                text(
                    "update users set failed_login_attempts=:attempts,locked_until=:locked where id=cast(:id as uuid)"
                ),
                {"id": self.actor.user_id, "attempts": attempts, "locked": locked_until},
            )
            await self.audit("iam.password.confirm", {}, "DENIED")
            await self.session.commit()
            raise APIError("IAM_PASSWORD_INVALID", "A senha atual não confere.", 403)
        await self.session.execute(
            text(
                "update users set failed_login_attempts=0,locked_until=null where id=cast(:id as uuid)"
            ),
            {"id": self.actor.user_id},
        )

    async def change_password(self, current: str, new: str) -> None:
        await self.begin()
        assert self.actor is not None
        await self._check_password(current)
        self.validate_password(new)
        await self.session.execute(
            text(
                "update users set password_hash=:password,updated_at=now() where id=cast(:id as uuid)"
            ),
            {"id": self.actor.user_id, "password": hash_password(new)},
        )
        await revoke_access(self.session, self.actor.user_id)
        await self.finish("iam.password.changed", {"target_user_id": self.actor.user_id})

    @staticmethod
    def validate_password(password: str) -> None:
        if not settings.password_reset_min_length <= len(password) <= 512:
            raise APIError(
                "PASSWORD_TOO_SHORT",
                f"A senha deve possuir entre {settings.password_reset_min_length} e 512 caracteres.",
                422,
            )

    async def _email_token(self, user_id: str, purpose: str, email: str) -> str:
        row = (
            (
                await self.session.execute(
                    text("select email,is_active from users where id=cast(:id as uuid)"),
                    {"id": user_id},
                )
            )
            .mappings()
            .one()
        )
        if not row["is_active"]:
            raise APIError("IAM_USER_INACTIVE", "Ative a conta antes de enviar o convite.", 409)
        recent = await self.session.scalar(
            text(
                "select count(*) from identity_email_tokens where user_id=cast(:id as uuid) and created_at>now()-interval '60 seconds'"
            ),
            {"id": user_id},
        )
        if recent:
            raise APIError("IAM_EMAIL_RATE_LIMIT", "Aguarde um minuto antes de reenviar.", 429)
        await self.session.execute(
            text(
                "update identity_email_tokens set used_at=coalesce(used_at,now()) where user_id=cast(:id as uuid)"
            ),
            {"id": user_id},
        )
        token = secrets.token_urlsafe(32)
        await self.session.execute(
            text("""
            insert into identity_email_tokens(user_id,token_hash,purpose,target_email,original_email,expires_at)
            values(cast(:id as uuid),:hash,:purpose,:email,:original,:expires)
        """),
            {
                "id": user_id,
                "hash": hash_opaque_token(token),
                "purpose": purpose,
                "email": email.lower(),
                "original": row["email"],
                "expires": datetime.now(UTC) + timedelta(hours=24 if purpose == "invite" else 1),
            },
        )
        await self.finish("iam.email.requested", {"target_user_id": user_id, "purpose": purpose})
        return token

    async def invite(self, user_id: str) -> bool:
        await self.begin("users.manage")
        value = await self.target(user_id)
        purpose = (
            "invite"
            if value["verification_required"] and not value["email_verified_at"]
            else "verify"
        )
        token = await self._email_token(user_id, purpose, value["email"])
        return await self.send_link(value["email"], token, purpose)

    async def verify_email(self) -> bool:
        await self.begin()
        assert self.actor is not None
        value = await self.user(self.actor.user_id)
        token = await self._email_token(self.actor.user_id, "verify", value["email"])
        return await self.send_link(value["email"], token, "verify")

    async def change_email(self, email: str, password: str) -> bool:
        await self.begin()
        assert self.actor is not None
        await self._check_password(password)
        await self._email_available(email, self.actor.user_id)
        token = await self._email_token(self.actor.user_id, "change_email", email)
        return await self.send_link(email, token, "change_email")

    async def send_link(self, email: str, token: str, purpose: str) -> bool:
        # TenantContext.hostname is resolved against the registered, active domains.
        scheme = "http" if settings.app_env == "development" else "https"
        url = f"{scheme}://{self.context.hostname}/api/v1/access/confirm-page#token={token}&purpose={purpose}"
        subject = (
            "Convite de acesso — Scheduler Pro"
            if purpose == "invite"
            else "Confirme seu e-mail — Scheduler Pro"
        )
        body = f"{subject}\n\nAcesse o endereço para confirmar: {url}\n\nO link é de uso único e expira em {'24 horas' if purpose == 'invite' else '1 hora'}.\nSe não reconhece a solicitação, ignore esta mensagem."
        try:
            sender = TenantMailService(self.session)
            row = await sender._row()
            config = None
            if row and row["enabled"]:
                mode = await sender._delivery_mode()
                config = sender._platform_config() if mode == "platform" else await sender.config()
            # The token is already committed; SMTP failures never delete a created account.
            await self.session.commit()
            if config:
                await asyncio.to_thread(sender._send_sync, config, email, subject, body)
                return True
            message = mail_delivery._base_message(recipient=email, subject=subject)
            if message is not None:
                message.set_content(body)
            result = await asyncio.to_thread(
                mail_delivery._send, message, purpose="identidade de usuário"
            )
            return result.delivered
        except Exception as exc:
            await self.session.rollback()
            logger.warning(
                "identity_email_delivery_failed", extra={"error_type": type(exc).__name__}
            )
            return False

    async def confirm_email(self, token: str, password: str | None) -> None:
        await lock_identity(self.session)
        self.admins_before = await self._admin_count()
        row = (
            (
                await self.session.execute(
                    text("""
            select t.*,u.email,u.is_active from identity_email_tokens t join users u on u.id=t.user_id
            where token_hash=:hash for update of t,u
        """),
                    {"hash": hash_opaque_token(token)},
                )
            )
            .mappings()
            .first()
        )
        if (
            row is None
            or row["used_at"]
            or row["expires_at"] <= datetime.now(UTC)
            or not row["is_active"]
            or row["email"] != row["original_email"]
        ):
            raise APIError(
                "IAM_EMAIL_TOKEN_INVALID", "Link inválido, já utilizado ou expirado.", 400
            )
        user_id = str(row["user_id"])
        await self._email_available(row["target_email"], user_id)
        if row["purpose"] == "invite":
            self.validate_password(password or "")
            await self.session.execute(
                text("update users set password_hash=:password where id=cast(:id as uuid)"),
                {"id": user_id, "password": hash_password(password or "")},
            )
        elif password is not None:
            raise APIError("IAM_PASSWORD_NOT_EXPECTED", "Este link confirma apenas o e-mail.", 422)
        await self.session.execute(
            text("""
            update users set email=:email,email_verified_at=now(),verification_required=false,
            failed_login_attempts=0,locked_until=null,updated_at=now() where id=cast(:id as uuid)
        """),
            {"id": user_id, "email": row["target_email"]},
        )
        # Does not enable disabled users, remove MFA or grant a role.
        await revoke_access(self.session, user_id)
        await self.finish(
            "iam.email.confirmed", {"target_user_id": user_id, "purpose": row["purpose"]}
        )

    async def professionals(self, q: str) -> list[dict[str, Any]]:
        rows = await self.session.execute(
            text(
                "select p.id::text,p.name,u.id::text as linked_user_id from professionals p left join users u on u.professional_id=p.id where lower(p.name) like :q order by lower(p.name),p.id limit 20"
            ),
            {"q": _pattern(q)},
        )
        return [dict(row) for row in rows.mappings()]

    async def audit_page(self, offset: int, user_id: str | None = None) -> dict[str, Any]:
        where = " where a.action like 'iam.%' and (cast(:user_id as text) is null or a.metadata->>'target_user_id'=:user_id or a.user_id::text=:user_id)"
        params = {"offset": offset, "user_id": user_id}
        rows = await self.session.execute(
            text(
                "select a.id::text,a.action,a.result,a.created_at,a.metadata,u.display_name as actor_name from audit_logs a left join users u on u.id=a.user_id"
                + where
                + " order by a.created_at desc,a.id limit 25 offset :offset"
            ),
            params,
        )
        count = await self.session.scalar(text("select count(*) from audit_logs a" + where), params)
        return {"items": [dict(row) for row in rows.mappings()], "total": count}
