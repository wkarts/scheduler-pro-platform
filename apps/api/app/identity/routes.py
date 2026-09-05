import asyncio
from hashlib import sha256
import base64
from io import BytesIO
import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import HTMLResponse, StreamingResponse

from app.api.deps import (
    get_current_tenant_user,
    get_tenant_context,
    get_tenant_session,
    get_platform_session,
)
from app.api.v1.routes.files import _stream
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.identity.images import AVATAR_PREFIX, MAX_AVATAR_BYTES, normalize_avatar
from app.identity.schemas import (
    ConfirmEmailInput,
    EmailInput,
    GroupInput,
    PasswordInput,
    ProfileInput,
    UserCreate,
    UserUpdate,
)
from app.identity.service import TenantIdentityService
from app.services.file_service import TenantFileService

router = APIRouter()
logger = logging.getLogger(__name__)


async def interactive(
    request: Request,
    response: Response,
    principal: AuthPrincipal = Depends(get_current_tenant_user),
) -> AuthPrincipal:
    if getattr(request.state, "integration_principal", None) is not None:
        raise APIError(
            "IAM_INTERACTIVE_REQUIRED",
            "Use uma sessão de usuário para administrar identidades.",
            403,
        )
    response.headers["Cache-Control"] = "no-store"
    return principal


async def service(
    principal: AuthPrincipal = Depends(interactive),
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> TenantIdentityService:
    return TenantIdentityService(session, context, principal)


def require(value: TenantIdentityService, *permissions: str) -> None:
    if value.actor is None or not value.actor.permissions.intersection(permissions):
        raise APIError("AUTH_PERMISSION_DENIED", "Permissão insuficiente.", 403)


@router.get("/catalog")
async def catalog(
    value: TenantIdentityService = Depends(service),
    platform_session: AsyncSession = Depends(get_platform_session),
) -> dict[str, Any]:
    data = await value.catalog()
    data["capabilities"] = list(
        (
            await platform_session.execute(
                text(
                    "select capability_key from tenant_capabilities where tenant_id=cast(:id as uuid) and enabled"
                ),
                {"id": value.context.tenant_id},
            )
        ).scalars()
    )
    data["tenant_id"] = value.context.tenant_id
    return success(data)


@router.get("/users")
async def users(
    q: str = Query("", max_length=160),
    offset: int = Query(0, ge=0, le=100000),
    value: TenantIdentityService = Depends(service),
) -> dict[str, Any]:
    require(value, "users.read")
    return success(await value.list_users(q, offset))


@router.get("/users/{user_id}")
async def user(user_id: UUID, value: TenantIdentityService = Depends(service)) -> dict[str, Any]:
    require(value, "users.read")
    return success(await value.user(str(user_id)))


@router.post("/users", status_code=201)
async def create_user(
    payload: UserCreate, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    return success(await value.create_user(payload.model_dump(mode="json")))


@router.put("/users/{user_id}")
async def update_user(
    user_id: UUID, payload: UserUpdate, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    return success(await value.update_user(str(user_id), payload.model_dump(mode="json")))


@router.post("/users/{user_id}/invite")
async def invite(user_id: UUID, value: TenantIdentityService = Depends(service)) -> dict[str, Any]:
    sent = await value.invite(str(user_id))
    return success(
        {
            "sent": sent,
            "message": "Convite enviado por e-mail."
            if sent
            else "Não foi possível enviar. Verifique o SMTP e reenvie o convite.",
        }
    )


@router.post("/users/{user_id}/revoke-access")
async def revoke_user(
    user_id: UUID, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    await value.revoke_user(str(user_id))
    return success({"revoked": True})


@router.get("/groups")
async def groups(value: TenantIdentityService = Depends(service)) -> dict[str, Any]:
    require(value, "users.read", "users.manage", "groups.manage")
    return success(await value.groups())


@router.post("/groups", status_code=201)
async def create_group(
    payload: GroupInput, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    return success(await value.save_group(payload.model_dump()))


@router.put("/groups/{group_id}")
async def update_group(
    group_id: UUID, payload: GroupInput, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    return success(await value.save_group(payload.model_dump(), str(group_id)))


@router.get("/professionals")
async def professionals(
    q: str = Query("", max_length=160), value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    require(value, "users.manage")
    return success(await value.professionals(q))


@router.get("/audit")
async def audit(
    offset: int = Query(0, ge=0, le=100000),
    user_id: UUID | None = None,
    value: TenantIdentityService = Depends(service),
) -> dict[str, Any]:
    require(value, "audit.read")
    return success(await value.audit_page(offset, str(user_id) if user_id else None))


@router.get("/profile")
async def profile(value: TenantIdentityService = Depends(service)) -> dict[str, Any]:
    assert value.actor is not None
    return success(await value.user(value.actor.user_id))


@router.put("/profile")
async def update_profile(
    payload: ProfileInput, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    return success(await value.update_profile(payload.model_dump()))


@router.post("/profile/password")
async def password(
    payload: PasswordInput, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    await value.change_password(payload.current_password, payload.new_password)
    return success({"changed": True, "login_required": True})


@router.post("/profile/email")
async def email(
    payload: EmailInput, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    return success({"sent": await value.change_email(str(payload.email), payload.current_password)})


@router.post("/profile/verify-email")
async def verify_email(value: TenantIdentityService = Depends(service)) -> dict[str, Any]:
    return success({"sent": await value.verify_email()})


async def _delete_avatar(storage: TenantFileService, key: str | None) -> None:
    if key and key.startswith(AVATAR_PREFIX):
        try:
            await storage.delete(key)
        except Exception as exc:
            # The old key is private and no longer referenced. Report cleanup without disclosing it.
            logger.warning("avatar_cleanup_pending", extra={"error_type": type(exc).__name__})


@router.put("/profile/avatar")
async def upload_avatar(
    request: Request, value: TenantIdentityService = Depends(service)
) -> dict[str, Any]:
    assert value.actor is not None
    await value.session.rollback()
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_AVATAR_BYTES:
            raise APIError("AVATAR_SIZE", "A foto deve ter até 2 MB.", 413)
        data.extend(chunk)
    image = await asyncio.to_thread(normalize_avatar, bytes(data))
    storage = TenantFileService(value.context)
    key = f"{AVATAR_PREFIX}{value.actor.user_id}/{uuid4().hex}.jpg"
    await value.session.rollback()  # No SQL connection is held while uploading.
    await storage.upload(key, BytesIO(image), "image/jpeg")
    try:
        await value.begin()
        old = await value.session.scalar(
            text("select avatar_key from users where id=cast(:id as uuid)"),
            {"id": value.actor.user_id},
        )
        await value.session.execute(
            text("update users set avatar_key=:key,updated_at=now() where id=cast(:id as uuid)"),
            {"id": value.actor.user_id, "key": key},
        )
        await value.finish(
            "iam.profile.avatar", {"target_user_id": value.actor.user_id, "operation": "replace"}
        )
    except Exception:
        await value.session.rollback()
        await _delete_avatar(storage, key)
        raise
    await _delete_avatar(storage, old)
    return success({"has_avatar": True})


@router.get("/profile/avatar")
async def get_avatar(value: TenantIdentityService = Depends(service)) -> StreamingResponse:
    assert value.actor is not None
    key = await value.session.scalar(
        text("select avatar_key from users where id=cast(:id as uuid)"), {"id": value.actor.user_id}
    )
    if not key or not key.startswith(f"{AVATAR_PREFIX}{value.actor.user_id}/"):
        raise APIError("AVATAR_NOT_FOUND", "Foto não cadastrada.", 404)
    await value.session.rollback()
    result = await TenantFileService(value.context).get_object(key)
    return StreamingResponse(
        _stream(result["Body"]),
        media_type="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": 'inline; filename="perfil.jpg"',
        },
    )


@router.delete("/profile/avatar")
async def delete_avatar(value: TenantIdentityService = Depends(service)) -> dict[str, Any]:
    assert value.actor is not None
    await value.begin()
    key = await value.session.scalar(
        text("select avatar_key from users where id=cast(:id as uuid)"), {"id": value.actor.user_id}
    )
    await value.session.execute(
        text("update users set avatar_key=null,updated_at=now() where id=cast(:id as uuid)"),
        {"id": value.actor.user_id},
    )
    await value.finish(
        "iam.profile.avatar", {"target_user_id": value.actor.user_id, "operation": "remove"}
    )
    await _delete_avatar(TenantFileService(value.context), key)
    return success({"has_avatar": False})


@router.post("/confirm-email")
async def confirm_email(
    payload: ConfirmEmailInput,
    response: Response,
    context: TenantContext = Depends(get_tenant_context),
    session: AsyncSession = Depends(get_tenant_session),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    await TenantIdentityService(session, context).confirm_email(payload.token, payload.new_password)
    return success({"confirmed": True, "login_required": True})


CONFIRM_SCRIPT = """
const params = new URLSearchParams(location.hash.slice(1));
let token = params.get('token') || '';
const invitation = params.get('purpose') === 'invite';
history.replaceState(null, '', location.pathname);
const form = document.querySelector('form'), message = document.getElementById('message');
const password = document.getElementById('password'), confirmation = document.getElementById('confirmation');
document.getElementById('passwords').hidden = !invitation;
password.required = confirmation.required = invitation;
form.addEventListener('submit', async event => {
  event.preventDefault();
  if (invitation && password.value !== confirmation.value) { message.textContent = 'As senhas não conferem.'; return; }
  const button = form.querySelector('button'); button.disabled = true;
  try {
    const response = await fetch('/api/v1/access/confirm-email', {method:'POST',cache:'no-store',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({token,...(invitation?{new_password:password.value}:{})})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || 'Não foi possível confirmar.');
    token = ''; password.value = confirmation.value = ''; form.hidden = true;
    message.textContent = 'E-mail confirmado. Entre com seu e-mail e senha para continuar.';
    document.getElementById('login').hidden = false;
  } catch (error) { message.textContent = error.message || 'Falha temporária de conexão.'; }
  finally { button.disabled = false; }
});
"""


@router.get("/confirm-page", response_class=HTMLResponse, include_in_schema=False)
async def confirm_page(_: TenantContext = Depends(get_tenant_context)) -> HTMLResponse:
    digest = base64.b64encode(sha256(CONFIRM_SCRIPT.encode()).digest()).decode()
    return HTMLResponse(
        '''<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>Confirmar acesso — Scheduler Pro</title><style>body{font:16px system-ui;background:#f4f7fc;color:#172b48;padding:24px}main{max-width:440px;margin:6vh auto;background:white;border:1px solid #dce5f0;border-radius:16px;padding:24px}form,label{display:grid;gap:12px}input,button,a{font:inherit;padding:12px;border-radius:8px;border:1px solid #b9cbe3}button{background:#254aa5;color:white;cursor:pointer}p{line-height:1.6}#passwords{display:grid;gap:12px}[hidden]{display:none!important}</style></head><body><main><small>SCHEDULER PRO</small><h1>Confirmar seu e-mail</h1><p>Confirme para concluir sua solicitação. Este link é de uso único.</p><form><div id="passwords"><label>Nova senha<input id="password" type="password" autocomplete="new-password" minlength="'''
        + str(settings_min_password())
        + """" maxlength="512"></label><label>Repita a senha<input id="confirmation" type="password" autocomplete="new-password" maxlength="512"></label></div><button type="submit">Confirmar</button></form><p id="message" role="status" aria-live="polite"></p><a id="login" href="/" hidden>Entrar na aplicação</a></main><script>"""
        + CONFIRM_SCRIPT
        + """</script></body></html>""",
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": f"default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-{digest}'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        },
    )


def settings_min_password() -> int:
    from app.core.config import settings

    return settings.password_reset_min_length
