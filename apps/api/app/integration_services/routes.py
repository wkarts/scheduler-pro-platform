from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from secrets import token_urlsafe
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.api.deps import get_current_platform_user, get_current_tenant_user
from app.core.errors import APIError
from app.core.secrets import seal_secret
from app.integration_services.auth import (
    IntegrationIdentity,
    audit,
    integration_session,
    public_row,
)
from app.integration_services.catalog import event_catalog, operation_catalog, scopes_catalog
from app.integration_services.config import integration_settings as config
from app.integration_services.webhooks import (
    UnsafeWebhookTarget,
    enqueue_test,
    resolve_public_addresses,
)


class TokenInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    scopes: list[str] = Field(min_length=1, max_length=100)
    expires_in_days: int | None = Field(default=None, ge=1, le=365, strict=True)
    rate_limit: int = Field(default=120, ge=1, le=1000)


class TokenValidityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expires_in_days: int | None = Field(ge=1, le=365, strict=True)


class WebhookInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=2, max_length=100)
    url: str = Field(min_length=10, max_length=2048)
    events: list[str] = Field(min_length=1, max_length=100)
    active: bool = True
    authorization_token: str | None = Field(default=None, max_length=2048)
    clear_authorization: bool = False


class OutcomeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    note: str = Field(min_length=10, max_length=500)
    reviewed: bool


class ActiveInput(BaseModel):
    active: bool


def identity(
    request: Request, *, manage: bool = True, interactive: bool = False
) -> IntegrationIdentity:
    value = getattr(request.state, "integration_identity", None)
    if not isinstance(value, IntegrationIdentity):
        raise APIError("AUTH_REQUIRED", "Autenticação obrigatória.", 401)
    if interactive and value.token_id:
        raise APIError(
            "INTERACTIVE_SESSION_REQUIRED", "Gerencie tokens pela sessão interativa.", 403
        )
    permission = "integrations.manage" if value.platform else "tenant.manage"
    if (
        manage
        and permission not in value.principal.permissions
        and not value.principal.is_super_admin
    ):
        raise APIError(
            "AUTH_PERMISSION_DENIED", "Permissão para gerenciar integrações obrigatória.", 403
        )
    return value


def webhook_identity(request: Request) -> IntegrationIdentity:
    current = identity(request)
    if current.platform and not current.control_plane_global:
        raise APIError(
            "GLOBAL_WEBHOOK_ACCESS_REQUIRED",
            "Webhooks globais exigem um administrador global ou seu token delegado.",
            403,
        )
    return current


def data(payload: Any) -> dict[str, Any]:
    return {"data": payload}


TOKEN_FIELDS = (
    "id::text,owner_id::text,name,prefix,scopes,permissions,tenant_ids,global_scope,rate_limit,"
    "created_at,expires_at,last_used_at,revoked_at"
)
ENDPOINT_FIELDS = (
    "id::text,name,url,events,active,created_by::text,created_at,updated_at,"
    "(authorization_ref is not null) as has_authorization"
)


def build_router(platform: bool) -> APIRouter:
    principal_dep = get_current_platform_user if platform else get_current_tenant_user
    router = APIRouter(
        dependencies=[Depends(principal_dep)], tags=["API Services / Webhook Services"]
    )

    @router.get("/catalog")
    async def catalog(request: Request) -> dict[str, Any]:
        current = identity(request, manage=False)
        return data(
            {
                "scope": "platform" if current.platform else "tenant",
                "api_enabled": config.api_enabled,
                "webhooks_enabled": config.webhooks_enabled,
                "incoming_webhooks_enabled": config.incoming_webhooks_enabled,
                "inbox_max_bytes": config.inbox_max_bytes,
                "scopes": scopes_catalog(platform),
                "events": event_catalog(platform),
                "operations": operation_catalog(request.app, platform),
                "replay_hours": config.replay_hours,
                "retention_days": config.retention_days,
                "max_request_bytes": config.max_request_bytes,
                "webhook_management_allowed": not platform or current.control_plane_global,
                "excluded": [
                    "login, refresh e MFA",
                    "emissão de tokens por tokens",
                    "operações que exigem superadministrador interativo",
                    "SSE stream",
                ],
            }
        )

    @router.get("/openapi")
    async def openapi(request: Request) -> JSONResponse:
        identity(request, manage=False)
        document = deepcopy(request.app.openapi())
        document["info"]["title"] = "Scheduler Pro — " + (
            "Control Plane" if platform else "Empresa"
        )
        paths: dict[str, Any] = {}
        for operation in operation_catalog(request.app, platform):
            path, method = operation["path"], operation["method"].lower()
            original = document["paths"].get(path, {}).get(method)
            if original is None:
                continue
            original["security"] = [{"ServiceToken": []}]
            original["x-service-scope"] = operation["scope"]
            if operation["idempotency_required"]:
                original.setdefault("parameters", []).append(
                    {
                        "name": "Idempotency-Key",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string", "minLength": 8, "maxLength": 128},
                    }
                )
            paths.setdefault(path, {})[method] = original
        document["paths"] = paths
        document.setdefault("components", {}).setdefault("securitySchemes", {})["ServiceToken"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "opaque",
            "description": "Token individual criado em API Services; não é um JWT de usuário.",
        }
        return JSONResponse(
            document,
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": 'attachment; filename="scheduler-services-openapi.json"',
            },
        )

    @router.get("/tokens")
    async def tokens(request: Request) -> dict[str, Any]:
        current = identity(request, interactive=True)
        async with integration_session(current.context) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            f"select {TOKEN_FIELDS} from service_api_tokens "
                            "where (:global_access or owner_id=cast(:owner as uuid)) order by created_at desc limit 500"
                        ),
                        {
                            "global_access": not platform or current.control_plane_global,
                            "owner": current.principal.user_id,
                        },
                    )
                )
                .mappings()
                .all()
            )
            return data([public_row(row) for row in rows])

    @router.post("/tokens", status_code=201)
    async def create_token(request: Request, body: TokenInput) -> dict[str, Any]:
        current = identity(request, interactive=True)
        known = {row["key"] for row in scopes_catalog(platform)}
        if not set(body.scopes).issubset(known):
            raise APIError("API_SCOPES_INVALID", "Escopo não pertence a este ambiente.", 422)
        identifier = uuid4()
        raw = f"sp_{'p' if platform else 't'}_{identifier.hex}.{token_urlsafe(32)}"
        async with integration_session(current.context) as session:
            # Serialize credential quotas only; this never locks a business transaction.
            await session.execute(text("select pg_advisory_xact_lock(7313,1)"))
            count = (
                await session.execute(
                    text(
                        "select count(*) from service_api_tokens where revoked_at is null and (expires_at is null or expires_at>now())"
                    )
                )
            ).scalar_one()
            if count >= config.max_tokens:
                raise APIError("API_TOKEN_QUOTA", "Limite de tokens ativos atingido.", 409)
            row = (
                (
                    await session.execute(
                        text(
                            "insert into service_api_tokens(id,owner_id,name,token_hash,prefix,scopes,permissions,roles,tenant_ids,global_scope,"
                            "expires_at,rate_limit) values(cast(:id as uuid),cast(:owner as uuid),:name,:hash,:prefix,"
                            "cast(:scopes as jsonb),cast(:permissions as jsonb),cast(:roles as jsonb),cast(:tenants as jsonb),:global_scope,:expires,:rate) "
                            f"returning {TOKEN_FIELDS}"
                        ),
                        {
                            "id": str(identifier),
                            "owner": current.principal.user_id,
                            "name": body.name.strip(),
                            "hash": sha256(raw.encode()).hexdigest(),
                            "prefix": raw[:18],
                            "scopes": json.dumps(sorted(set(body.scopes))),
                            "permissions": json.dumps(sorted(current.principal.permissions)),
                            "roles": json.dumps(sorted(current.principal.roles)),
                            "tenants": json.dumps(sorted(current.principal.tenant_ids)),
                            "global_scope": current.control_plane_global,
                            "expires": (datetime.now(UTC) + timedelta(days=body.expires_in_days))
                            if body.expires_in_days is not None
                            else None,
                            "rate": body.rate_limit,
                        },
                    )
                )
                .mappings()
                .one()
            )
            await audit(session, current.principal.user_id, "api_token.created", str(identifier))
            await session.commit()
            return data({**public_row(row), "token": raw})

    @router.post("/tokens/{token_id}/rotate")
    async def rotate_token(request: Request, token_id: UUID) -> dict[str, Any]:
        current = identity(request, interactive=True)
        raw = f"sp_{'p' if platform else 't'}_{token_id.hex}.{token_urlsafe(32)}"
        async with integration_session(current.context) as session:
            row = (
                (
                    await session.execute(
                        text(
                            "update service_api_tokens set token_hash=:hash,prefix=:prefix "
                            "where id=cast(:id as uuid) and owner_id=cast(:owner as uuid) "
                            "and revoked_at is null and (expires_at is null or expires_at>now()) "
                            f"returning {TOKEN_FIELDS}"
                        ),
                        {
                            "id": str(token_id),
                            "owner": current.principal.user_id,
                            "hash": sha256(raw.encode()).hexdigest(),
                            "prefix": raw[:18],
                        },
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("API_TOKEN_NOT_FOUND", "Token ativo não encontrado.", 404)
            await audit(session, current.principal.user_id, "api_token.rotated", str(token_id))
            await session.commit()
            return data({**public_row(row), "token": raw})

    @router.patch("/tokens/{token_id}/validity")
    async def token_validity(
        request: Request, token_id: UUID, body: TokenValidityInput
    ) -> dict[str, Any]:
        current = identity(request, interactive=True)
        expires = (
            (datetime.now(UTC) + timedelta(days=body.expires_in_days))
            if body.expires_in_days is not None
            else None
        )
        async with integration_session(current.context) as session:
            row = (
                (
                    await session.execute(
                        text(
                            "update service_api_tokens set expires_at=:expires "
                            "where id=cast(:id as uuid) and owner_id=cast(:owner as uuid) "
                            "and revoked_at is null and (expires_at is null or expires_at>now()) "
                            f"returning {TOKEN_FIELDS}"
                        ),
                        {
                            "expires": expires,
                            "id": str(token_id),
                            "owner": current.principal.user_id,
                        },
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("API_TOKEN_NOT_FOUND", "Token ativo do titular não encontrado.", 404)
            await audit(
                session, current.principal.user_id, "api_token.validity_changed", str(token_id)
            )
            await session.commit()
            return data(public_row(row))

    @router.delete("/tokens/{token_id}")
    async def revoke_token(request: Request, token_id: UUID) -> dict[str, Any]:
        current = identity(request, interactive=True)
        async with integration_session(current.context) as session:
            identifier = (
                await session.execute(
                    text(
                        "update service_api_tokens set revoked_at=coalesce(revoked_at,now()) "
                        "where id=cast(:id as uuid) and (:global_access or owner_id=cast(:owner as uuid)) returning id::text"
                    ),
                    {
                        "id": str(token_id),
                        "global_access": not platform or current.control_plane_global,
                        "owner": current.principal.user_id,
                    },
                )
            ).scalar_one_or_none()
            if identifier is None:
                raise APIError("API_TOKEN_NOT_FOUND", "Token não encontrado.", 404)
            await audit(session, current.principal.user_id, "api_token.revoked", str(token_id))
            await session.commit()
            return data({"id": identifier, "revoked": True})

    @router.get("/webhooks")
    async def webhooks(request: Request) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            f"select {ENDPOINT_FIELDS} from service_webhook_endpoints "
                            "where deleted_at is null order by created_at desc limit 100"
                        )
                    )
                )
                .mappings()
                .all()
            )
            return data([dict(row) for row in rows])

    async def validate_webhook(body: WebhookInput) -> None:
        if not set(body.events).issubset(set(event_catalog(platform)) | {"*"}):
            raise APIError("WEBHOOK_EVENTS_INVALID", "Eventos não pertencem a este ambiente.", 422)
        if body.authorization_token and any(
            ord(c) < 32 or ord(c) > 126 for c in body.authorization_token
        ):
            raise APIError("WEBHOOK_AUTH_INVALID", "Credencial HTTP inválida.", 422)
        try:
            await resolve_public_addresses(body.url)
        except UnsafeWebhookTarget as exc:
            raise APIError("WEBHOOK_TARGET_BLOCKED", str(exc), 422) from exc
        except Exception as exc:
            raise APIError(
                "WEBHOOK_DNS_UNAVAILABLE", "Não foi possível validar o DNS do destino.", 422
            ) from exc

    @router.post("/webhooks", status_code=201)
    async def create_webhook(request: Request, body: WebhookInput) -> dict[str, Any]:
        current = webhook_identity(request)
        await validate_webhook(body)
        identifier = str(uuid4())
        secret = "whsec_" + token_urlsafe(32)
        async with integration_session(current.context) as session:
            await session.execute(text("select pg_advisory_xact_lock(7313,2)"))
            count = (
                await session.execute(
                    text("select count(*) from service_webhook_endpoints where deleted_at is null")
                )
            ).scalar_one()
            if count >= config.max_endpoints:
                raise APIError("WEBHOOK_QUOTA", "Limite de destinos atingido.", 409)
            row = (
                (
                    await session.execute(
                        text(
                            "insert into service_webhook_endpoints(id,name,url,events,secret_ref,authorization_ref,"
                            "active,created_by) values(cast(:id as uuid),:name,:url,cast(:events as jsonb),"
                            ":secret,:authorization,:active,cast(:actor as uuid)) "
                            f"returning {ENDPOINT_FIELDS}"
                        ),
                        {
                            "id": identifier,
                            "name": body.name.strip(),
                            "url": body.url,
                            "events": json.dumps(sorted(set(body.events))),
                            "secret": seal_secret(secret),
                            "authorization": seal_secret(body.authorization_token)
                            if body.authorization_token
                            else None,
                            "active": body.active,
                            "actor": current.principal.user_id,
                        },
                    )
                )
                .mappings()
                .one()
            )
            await audit(session, current.principal.user_id, "webhook.created", identifier)
            await session.commit()
            return data({**dict(row), "signing_secret": secret})

    @router.put("/webhooks/{endpoint_id}")
    async def update_webhook(
        request: Request, endpoint_id: UUID, body: WebhookInput
    ) -> dict[str, Any]:
        current = webhook_identity(request)
        await validate_webhook(body)
        async with integration_session(current.context) as session:
            row = (
                (
                    await session.execute(
                        text(
                            "update service_webhook_endpoints set name=:name,url=:url,events=cast(:events as jsonb),"
                            "active=:active,updated_at=now(),authorization_ref=case when :clear then null "
                            "else coalesce(:authorization,authorization_ref) end "
                            "where id=cast(:id as uuid) and deleted_at is null "
                            f"returning {ENDPOINT_FIELDS}"
                        ),
                        {
                            "id": str(endpoint_id),
                            "name": body.name.strip(),
                            "url": body.url,
                            "events": json.dumps(sorted(set(body.events))),
                            "active": body.active,
                            "clear": body.clear_authorization,
                            "authorization": seal_secret(body.authorization_token)
                            if body.authorization_token
                            else None,
                        },
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("WEBHOOK_NOT_FOUND", "Destino não encontrado.", 404)
            await audit(session, current.principal.user_id, "webhook.updated", str(endpoint_id))
            await session.commit()
            return data(dict(row))

    @router.patch("/webhooks/{endpoint_id}/status")
    async def webhook_status(
        request: Request, endpoint_id: UUID, body: ActiveInput
    ) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            row = (
                (
                    await session.execute(
                        text(
                            "update service_webhook_endpoints set active=:active,updated_at=now() "
                            "where id=cast(:id as uuid) and deleted_at is null "
                            f"returning {ENDPOINT_FIELDS}"
                        ),
                        {"id": str(endpoint_id), "active": body.active},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("WEBHOOK_NOT_FOUND", "Destino não encontrado.", 404)
            await audit(
                session, current.principal.user_id, "webhook.status_changed", str(endpoint_id)
            )
            await session.commit()
            return data(dict(row))

    @router.post("/webhooks/{endpoint_id}/rotate-secret")
    async def rotate_webhook(request: Request, endpoint_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        secret = "whsec_" + token_urlsafe(32)
        async with integration_session(current.context) as session:
            row = (
                await session.execute(
                    text(
                        "update service_webhook_endpoints set secret_ref=:secret,updated_at=now() "
                        "where id=cast(:id as uuid) and deleted_at is null returning id::text"
                    ),
                    {"id": str(endpoint_id), "secret": seal_secret(secret)},
                )
            ).scalar_one_or_none()
            if row is None:
                raise APIError("WEBHOOK_NOT_FOUND", "Destino não encontrado.", 404)
            await audit(
                session, current.principal.user_id, "webhook.secret_rotated", str(endpoint_id)
            )
            await session.commit()
            return data({"id": row, "signing_secret": secret})

    @router.delete("/webhooks/{endpoint_id}")
    async def remove_webhook(request: Request, endpoint_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            row = (
                await session.execute(
                    text(
                        "update service_webhook_endpoints set active=false,deleted_at=coalesce(deleted_at,now()),"
                        "authorization_ref=null,secret_ref='' where id=cast(:id as uuid) returning id::text"
                    ),
                    {"id": str(endpoint_id)},
                )
            ).scalar_one_or_none()
            if row is None:
                raise APIError("WEBHOOK_NOT_FOUND", "Destino não encontrado.", 404)
            await audit(session, current.principal.user_id, "webhook.deleted", str(endpoint_id))
            await session.commit()
            return data({"id": row, "deleted": True})

    @router.post("/webhooks/{endpoint_id}/test", status_code=202)
    async def test_webhook(request: Request, endpoint_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        delivery = await enqueue_test(current.context, str(endpoint_id))
        return data({"delivery_id": delivery, "status": "pending"})

    @router.get("/deliveries")
    async def deliveries(request: Request, offset: int = 0, limit: int = 50) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "select d.id::text,d.endpoint_id::text,e.name,d.event_id::text,v.event_type,d.state,"
                            "d.attempts,d.cycle_attempts,d.available_at,d.http_status,d.last_error,d.created_at,"
                            "d.delivered_at from service_webhook_deliveries d "
                            "join service_webhook_endpoints e on e.id=d.endpoint_id "
                            "join service_webhook_events v on v.id=d.event_id "
                            "order by d.created_at desc,d.id desc limit :limit offset :offset"
                        ),
                        {"limit": min(max(limit, 1), 100), "offset": min(max(offset, 0), 100000)},
                    )
                )
                .mappings()
                .all()
            )
            return data([dict(row) for row in rows])

    @router.get("/deliveries/{delivery_id}/attempts")
    async def delivery_attempts(request: Request, delivery_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "select attempt,started_at,finished_at,http_status,error from service_webhook_attempts "
                            "where delivery_id=cast(:id as uuid) order by started_at desc limit 100"
                        ),
                        {"id": str(delivery_id)},
                    )
                )
                .mappings()
                .all()
            )
            return data([dict(row) for row in rows])

    @router.post("/deliveries/{delivery_id}/retry", status_code=202)
    async def retry_delivery(request: Request, delivery_id: UUID) -> dict[str, Any]:
        current = webhook_identity(request)
        async with integration_session(current.context) as session:
            row = (
                await session.execute(
                    text(
                        "update service_webhook_deliveries d set state='pending',cycle_attempts=0,"
                        "available_at=now(),lease_id=null,lease_until=null where d.id=cast(:id as uuid) "
                        "and d.state in ('failed','cancelled') and exists(select 1 from service_webhook_endpoints e "
                        "where e.id=d.endpoint_id and e.active and e.deleted_at is null) returning d.id::text"
                    ),
                    {"id": str(delivery_id)},
                )
            ).scalar_one_or_none()
            if row is None:
                raise APIError(
                    "WEBHOOK_RETRY_NOT_ALLOWED",
                    "Entrega não está em falha ou o destino não está ativo.",
                    409,
                )
            await audit(
                session, current.principal.user_id, "webhook.delivery_retried", str(delivery_id)
            )
            await session.commit()
            return data({"delivery_id": row, "status": "pending"})

    @router.get("/requests")
    async def requests(request: Request, offset: int = 0) -> dict[str, Any]:
        current = identity(request, manage=False)
        clause = (
            "where actor_key=:actor"
            if current.token_id or (platform and not current.control_plane_global)
            else ""
        )
        if not current.token_id:
            identity(request)
        async with integration_session(current.context) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "select id::text,actor_key,method,path,state,response_status,created_at,completed_at "
                            f"from service_api_requests {clause} order by created_at desc,id desc limit 50 offset :offset"
                        ),
                        {"actor": current.actor_key, "offset": min(max(offset, 0), 100000)},
                    )
                )
                .mappings()
                .all()
            )
            return data([dict(row) for row in rows])

    @router.get("/requests/{request_id}")
    async def request_status(request: Request, request_id: UUID) -> dict[str, Any]:
        current = identity(request, manage=False)
        clause = (
            "and actor_key=:actor"
            if current.token_id or (platform and not current.control_plane_global)
            else ""
        )
        if not current.token_id:
            identity(request)
        async with integration_session(current.context) as session:
            row = (
                (
                    await session.execute(
                        text(
                            "select id::text,method,path,state,response_status,created_at,completed_at "
                            "from service_api_requests where id=cast(:id as uuid) " + clause
                        ),
                        {"id": str(request_id), "actor": current.actor_key},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise APIError("API_REQUEST_NOT_FOUND", "Operação não encontrada.", 404)
            return data(dict(row))

    @router.post("/requests/{request_id}/resolve-outcome")
    async def resolve_outcome(
        request: Request, request_id: UUID, body: OutcomeInput
    ) -> dict[str, Any]:
        current = identity(request, interactive=True)
        if not body.reviewed:
            raise APIError(
                "MANUAL_REVIEW_REQUIRED", "Confira o resultado da operação antes de resolver.", 422
            )
        async with integration_session(current.context) as session:
            row = (
                await session.execute(
                    text(
                        "update service_api_requests set state='resolved',resolution_note=:note,"
                        "completed_at=now() where id=cast(:id as uuid) "
                        "and (state='unknown' or (state='processing' and created_at<now()-interval '10 minutes')) "
                        "and (:global_access or actor_key=:actor) returning id::text"
                    ),
                    {
                        "id": str(request_id),
                        "note": body.note,
                        "actor": current.actor_key,
                        "global_access": not platform or current.control_plane_global,
                    },
                )
            ).scalar_one_or_none()
            if row is None:
                raise APIError(
                    "API_OUTCOME_NOT_RESOLVABLE", "Operação em execução ou já concluída.", 409
                )
            await audit(
                session, current.principal.user_id, "api_request.manually_reviewed", str(request_id)
            )
            await session.commit()
            return data({"id": row, "state": "resolved", "key_reusable": False})

    @router.get("/audit")
    async def integration_audit(request: Request) -> dict[str, Any]:
        current = identity(request)
        async with integration_session(current.context) as session:
            rows = (
                (
                    await session.execute(
                        text(
                            "select id::text,actor_id::text,action,resource_id::text,created_at "
                            "from service_integration_audit "
                            "where (:global_access or actor_id=cast(:actor as uuid)) "
                            "order by created_at desc limit 100"
                        ),
                        {
                            "global_access": not platform or current.control_plane_global,
                            "actor": current.principal.user_id,
                        },
                    )
                )
                .mappings()
                .all()
            )
            return data([dict(row) for row in rows])

    from app.integration_services.incoming import add_management_routes

    add_management_routes(router)
    return router
