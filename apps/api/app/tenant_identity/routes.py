import asyncio
import io
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_user, get_tenant_context, get_tenant_session
from app.core.errors import APIError
from app.core.responses import success
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.services.file_service import TenantFileService
from app.tenant_identity.avatar import MAX_UPLOAD, sanitize_avatar
from app.tenant_identity.schemas import (
    ConfirmationInput,
    EmailInput,
    GroupInput,
    PasswordInput,
    ProfileInput,
    UserCreate,
    UserUpdate,
)
from app.tenant_identity.service import IdentityService, revoke_access

router = APIRouter()


async def identity(
    response: Response,
    principal: AuthPrincipal = Depends(get_current_tenant_user),
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> IdentityService:
    response.headers["Cache-Control"] = "no-store"
    return IdentityService(session, context, principal)


@router.get("/catalog")
async def catalog(service: IdentityService = Depends(identity)) -> dict[str, Any]:
    return success(await service.catalog())


@router.get("/users")
async def users(
    q: str = Query("", max_length=160),
    offset: int = Query(0, ge=0, le=100000),
    service: IdentityService = Depends(identity),
) -> dict[str, Any]:
    return success(await service.users(q, offset))


@router.get("/users/{uid}")
async def user(uid: UUID, service: IdentityService = Depends(identity)) -> dict[str, Any]:
    return success(await service.user(str(uid)))


@router.post("/users", status_code=201)
async def create_user(
    payload: UserCreate, service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    return success(await service.create_user(payload.model_dump(mode="json")))


@router.put("/users/{uid}")
async def update_user(
    uid: UUID, payload: UserUpdate, service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    return success(await service.update_user(str(uid), payload.model_dump(mode="json")))


@router.post("/users/{uid}/invite")
async def invite(uid: UUID, service: IdentityService = Depends(identity)) -> dict[str, Any]:
    sent = await service.invite(str(uid))
    return success(
        {
            "sent": sent,
            "message": "Confirmação enviada."
            if sent
            else "Conta preservada. Configure o SMTP para enviar a confirmação.",
        }
    )


@router.post("/users/{uid}/revoke-access")
async def revoke(uid: UUID, service: IdentityService = Depends(identity)) -> dict[str, Any]:
    allowed = await service.authorize("users.manage", lock=True)
    await service._target(str(uid), allowed)
    await revoke_access(service.session, str(uid))
    await service.audit("iam.user.access_revoked", {"target_user_id": str(uid)})
    await service.session.commit()
    return success({"revoked": True})


@router.get("/groups")
async def groups(service: IdentityService = Depends(identity)) -> dict[str, Any]:
    return success(await service.groups())


@router.post("/groups", status_code=201)
async def create_group(
    payload: GroupInput, service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    return success(await service.save_group(None, payload.model_dump()))


@router.put("/groups/{gid}")
async def update_group(
    gid: UUID, payload: GroupInput, service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    return success(await service.save_group(str(gid), payload.model_dump()))


@router.get("/professionals")
async def professionals(
    q: str = Query("", max_length=160), service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    await service.authorize("users.manage")
    rows = (
        await service.session.execute(
            text(
                "select p.id::text,p.name,u.id::text as linked_user_id from professionals p left join users u on u.professional_id=p.id where p.name ilike :q order by p.name,p.id limit 20"
            ),
            {"q": f"%{q}%"},
        )
    ).mappings()
    return success([dict(r) for r in rows])


@router.get("/audit")
async def audit(
    offset: int = Query(0, ge=0, le=100000), service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    await service.authorize("users.audit")
    # Read only the identity/security log; no unrelated business or credential payloads.
    where = (
        "where a.action like 'iam.%' or a.action in ('auth.login','auth.password_reset.complete')"
    )
    total = await service.session.scalar(text(f"select count(*) from audit_logs a {where}"))
    rows = (
        await service.session.execute(
            text(
                f"select a.id::text,a.action,a.result,a.created_at,a.metadata,u.display_name as actor_name from audit_logs a left join users u on u.id=a.user_id {where} order by a.created_at desc,a.id limit 25 offset :offset"
            ),
            {"offset": offset},
        )
    ).mappings()
    return success({"items": [dict(r) for r in rows], "total": total})


@router.get("/profile")
async def profile(service: IdentityService = Depends(identity)) -> dict[str, Any]:
    return success(await service.profile())


@router.put("/profile")
async def update_profile(
    payload: ProfileInput, service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    return success(await service.update_profile(payload.model_dump()))


@router.post("/profile/password")
async def change_password(
    payload: PasswordInput, service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    await service.change_password(payload.current_password, payload.new_password)
    return success({"changed": True})


@router.post("/profile/email")
async def change_email(
    payload: EmailInput, service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    return success(
        {"sent": await service.request_email(str(payload.email), payload.current_password)}
    )


@router.post("/profile/verify-email")
async def request_verification(service: IdentityService = Depends(identity)) -> dict[str, Any]:
    return success({"sent": await service.request_email()})


@router.post("/confirm-email")
async def confirm_email(
    payload: ConfirmationInput,
    response: Response,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    await IdentityService(session, context).confirm(payload.token, payload.new_password)
    return success({"confirmed": True, "message": "E-mail confirmado. Entre com sua senha."})


@router.get("/profile/avatar")
async def avatar(service: IdentityService = Depends(identity)) -> Response:
    await service.authorize()
    assert service.actor
    key = await service.session.scalar(
        text("select avatar_key from users where id=cast(:id as uuid)"),
        {"id": service.actor.user_id},
    )
    await service.session.commit()
    if not key:
        raise APIError("AVATAR_NOT_FOUND", "Perfil sem foto.", 404)
    item = await TenantFileService(service.context).get_object(str(key))

    def read() -> bytes:
        try:
            body = bytes(item["Body"].read(MAX_UPLOAD + 1))
            if len(body) > MAX_UPLOAD:
                raise APIError("AVATAR_INVALID", "Foto armazenada inválida.", 422)
            return body
        finally:
            item["Body"].close()

    return Response(
        await asyncio.to_thread(read),
        media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.put("/profile/avatar")
async def upload_avatar(
    request: Request, service: IdentityService = Depends(identity)
) -> dict[str, Any]:
    await service.authorize()
    await service.session.commit()
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_UPLOAD:
            raise APIError("AVATAR_SIZE_INVALID", "A foto deve ter até 2 MB.", 413)
    image = await asyncio.to_thread(
        sanitize_avatar, bytes(data), request.headers.get("content-type", "").split(";")[0]
    )
    assert service.actor
    storage = TenantFileService(service.context)
    key = f"_identity/{service.actor.user_id}/{uuid4().hex}.png"
    await storage.upload(key, io.BytesIO(image), "image/png")
    try:
        await service.authorize(lock=True)
        old = await service.session.scalar(
            text("select avatar_key from users where id=cast(:id as uuid)"),
            {"id": service.actor.user_id},
        )
        await service.session.execute(
            text("update users set avatar_key=:key,updated_at=now() where id=cast(:id as uuid)"),
            {"id": service.actor.user_id, "key": key},
        )
        await service.audit(
            "iam.profile.avatar", {"target_user_id": service.actor.user_id, "removed": False}
        )
        await service.session.commit()
    except Exception:
        await service.session.rollback()
        # Keep an unreferenced object on uncertain commit rather than deleting a possibly used photo.
        raise
    if old:
        try:
            await storage.delete(str(old))
        except APIError:
            pass
    return success({"has_avatar": True})


@router.delete("/profile/avatar")
async def remove_avatar(service: IdentityService = Depends(identity)) -> dict[str, Any]:
    await service.authorize(lock=True)
    assert service.actor
    old = await service.session.scalar(
        text("select avatar_key from users where id=cast(:id as uuid)"),
        {"id": service.actor.user_id},
    )
    await service.session.execute(
        text("update users set avatar_key=null,updated_at=now() where id=cast(:id as uuid)"),
        {"id": service.actor.user_id},
    )
    await service.audit(
        "iam.profile.avatar", {"target_user_id": service.actor.user_id, "removed": True}
    )
    await service.session.commit()
    if old:
        await TenantFileService(service.context).delete(str(old))
    return success({"has_avatar": False})
