import json
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.config import settings
from app.core.errors import APIError
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.phone_normalization import PhoneNormalizationService
from app.services.whatsapp_provider import WhatsAppProvider, WhatsAppProviderFactory
from app.workers.celery_app import celery_app

router = APIRouter()

PUBLIC_PRODUCT_NAME = "ARGWS Whatsapp API"


class SendTextRequest(BaseModel):
    to: str = Field(min_length=8, max_length=80)
    message: str = Field(min_length=1, max_length=4096)


class PairingRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=80)


class TestSendRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=80)
    message: str = Field(
        default="Teste de comunicação do Scheduler Pro.",
        min_length=1,
        max_length=4096,
    )


def _as_image_data_uri(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    clean = value.strip()
    if not clean:
        return None
    if clean.startswith("data:image/"):
        return clean
    if len(clean) >= 512 and " " not in clean and "\n" not in clean:
        return f"data:image/png;base64,{clean}"
    return None


def _qr_payload(value: object) -> dict[str, Any] | None:
    """Normaliza os formatos históricos retornados pelo conector interno."""
    if isinstance(value, dict):
        base64_value = _as_image_data_uri(value.get("base64"))
        if base64_value is None:
            base64_value = _as_image_data_uri(value.get("qrcode"))
        if base64_value is None:
            base64_value = _as_image_data_uri(value.get("qr"))
        if base64_value is None:
            base64_value = _as_image_data_uri(value.get("code"))
        pairing_code = value.get("pairingCode") or value.get("pairing_code")
        raw_code = value.get("code")
        count = value.get("count")
        if base64_value or pairing_code or (
            isinstance(raw_code, str) and len(raw_code.strip()) > 20
        ):
            return {
                "base64": base64_value,
                "pairing_code": str(pairing_code) if pairing_code else None,
                "code": str(raw_code) if isinstance(raw_code, str) else None,
                "count": count if isinstance(count, int) else None,
            }
        for key in (
            "qrcode",
            "qrCode",
            "qr",
            "connection",
            "connect",
            "create",
            "ensure",
            "provider",
            "instance",
            "data",
            "result",
        ):
            if key in value:
                found = _qr_payload(value[key])
                if found:
                    return found
        for nested in value.values():
            found = _qr_payload(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _qr_payload(nested)
            if found:
                return found
    return None


def _provider_status_code(error: APIError) -> int:
    if not isinstance(error.details, dict):
        return 0
    raw = error.details.get("status_code")
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _public_provider_error(action: str, error: APIError) -> APIError:
    messages = {
        "connect": "Não foi possível iniciar a conexão com o WhatsApp. Tente novamente.",
        "pairing": "Não foi possível gerar o código de pareamento. Confira o telefone e tente novamente.",
        "status": "Não foi possível verificar a conexão com o WhatsApp.",
        "disconnect": "Não foi possível desconectar o WhatsApp. Tente novamente.",
        "send": "Não foi possível enviar a mensagem pelo WhatsApp.",
    }
    return APIError(
        f"ARGWS_WHATSAPP_{action.upper()}_FAILED",
        messages[action],
        503 if error.status_code in {424, 500, 502, 503, 504} else error.status_code,
    )


async def _tenant_provider(
    session: AsyncSession,
    context: TenantContext,
) -> tuple[str, WhatsAppProvider]:
    instance_name = await session.scalar(
        text(
            "select instance_name from whatsapp_integrations "
            "where name='default' limit 1"
        )
    )
    if not instance_name:
        instance_name = f"{settings.evolution_instance_name}-{context.slug}"[:160]
        await session.execute(
            text(
                """
                insert into whatsapp_integrations(
                    name, provider, instance_name, status, settings
                )
                values(
                    'default', 'evolution', :instance_name,
                    'DISCONNECTED', '{}'::jsonb
                )
                on conflict(name) do update
                set instance_name=excluded.instance_name
                """
            ),
            {"instance_name": instance_name},
        )
        await session.commit()
    return str(instance_name), WhatsAppProviderFactory.make(str(instance_name))


async def _persist_integration_state(
    session: AsyncSession,
    *,
    status: str,
    settings_data: dict[str, Any],
) -> None:
    await session.execute(
        text(
            """
            update whatsapp_integrations
            set status=:status,
                settings=cast(:settings as jsonb),
                updated_at=now()
            where name='default'
            """
        ),
        {
            "status": status,
            "settings": json.dumps(settings_data, ensure_ascii=False, default=str),
        },
    )


async def _stored_settings(session: AsyncSession) -> dict[str, Any]:
    value = await session.scalar(
        text("select settings from whatsapp_integrations where name='default' limit 1")
    )
    return dict(value) if isinstance(value, dict) else {}


async def _normalized_phone(session: AsyncSession, value: str) -> str:
    normalizer = await PhoneNormalizationService.from_session(session)
    normalized = normalizer.normalize(value, required=True)
    assert normalized is not None
    return normalized


async def _connect_response(
    session: AsyncSession,
    context: TenantContext,
) -> dict[str, Any]:
    instance_name, provider = await _tenant_provider(session, context)
    try:
        result = await provider.connect_instance()
    except APIError as exc:
        raise _public_provider_error("connect", exc) from exc

    qr = _qr_payload(result)
    stored_settings = await _stored_settings(session)
    stored_settings["last_connect"] = result
    stored_settings["connection_method"] = "QR_CODE"
    if qr is not None:
        stored_settings["last_qr"] = qr
    await _persist_integration_state(
        session,
        status="CONNECTING",
        settings_data=stored_settings,
    )
    await session.commit()
    return {
        "product": PUBLIC_PRODUCT_NAME,
        "instance_name": instance_name,
        "status": "CONNECTING",
        "qr": qr,
        # Campo legado mantido sem expor o payload/fornecedor interno.
        "provider": {"ok": True},
    }


@router.post("/connect")
async def connect(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Contrato histórico do Scheduler Pro para conexão por QR Code."""
    return success(await _connect_response(session, context))


@router.post("/connect/qr")
async def connect_qr(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Alias do mesmo fluxo de QR histórico; não cria outro conector."""
    return success(await _connect_response(session, context))


@router.post("/connect/pairing")
async def connect_pairing(
    payload: PairingRequest,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    phone = await _normalized_phone(session, payload.phone)
    instance_name, provider = await _tenant_provider(session, context)
    try:
        result = await provider.connect_pairing(phone)
    except APIError as exc:
        raise _public_provider_error("pairing", exc) from exc

    qr = _qr_payload(result)
    pairing_code = str((qr or {}).get("pairing_code") or "").strip() or None
    stored_settings = await _stored_settings(session)
    stored_settings["last_pairing"] = result
    stored_settings["connection_method"] = "PAIRING_CODE"
    stored_settings["connected_phone"] = phone
    if qr is not None:
        stored_settings["last_qr"] = qr
    await _persist_integration_state(
        session,
        status="CONNECTING",
        settings_data=stored_settings,
    )
    await session.commit()
    if pairing_code is None:
        raise APIError(
            "ARGWS_WHATSAPP_PAIRING_CODE_UNAVAILABLE",
            "O código de pareamento ainda não ficou disponível. Tente gerar novamente.",
            409,
        )
    return success(
        {
            "product": PUBLIC_PRODUCT_NAME,
            "instance_name": instance_name,
            "status": "CONNECTING",
            "phone": phone,
            "pairing_code": pairing_code,
            "qr": qr,
            "provider": {"ok": True},
        }
    )


@router.get("/status")
async def status(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    instance_name, provider = await _tenant_provider(session, context)
    existing = (
        await session.execute(
            text(
                "select status, settings from whatsapp_integrations "
                "where name='default' limit 1"
            )
        )
    ).mappings().first()
    stored_settings = (
        dict(existing["settings"])
        if existing and isinstance(existing.get("settings"), dict)
        else {}
    )
    previous_status = str(existing["status"] if existing else "DISCONNECTED").upper()

    try:
        result = await provider.connection_status()
    except APIError as exc:
        if _provider_status_code(exc) != 404:
            raise _public_provider_error("status", exc) from exc
        result = {
            "instance": {
                "state": "close",
                "status": "missing",
                "instanceName": instance_name,
            },
            "missing": True,
        }

    raw_instance = result.get("instance")
    instance_data: dict[str, Any] = (
        raw_instance if isinstance(raw_instance, dict) else {}
    )
    state = str(
        instance_data.get("state")
        or instance_data.get("status")
        or result.get("state")
        or "unknown"
    ).lower()
    if state in {"open", "connected"}:
        db_status = "CONNECTED"
    elif state in {"close", "closed", "disconnected", "missing"}:
        db_status = "DISCONNECTED"
    else:
        db_status = "CONNECTING"

    qr = _qr_payload(result)
    if qr is None and db_status != "CONNECTED":
        qr = _qr_payload(stored_settings.get("last_qr")) or _qr_payload(
            stored_settings.get("last_connect")
        ) or _qr_payload(stored_settings.get("last_pairing"))

    if qr is None and db_status != "CONNECTED" and previous_status == "CONNECTING":
        try:
            refreshed_connect = await provider.connect_instance()
            refreshed_qr = _qr_payload(refreshed_connect)
            stored_settings["last_connect"] = refreshed_connect
            if refreshed_qr is not None:
                qr = refreshed_qr
                stored_settings["last_qr"] = refreshed_qr
                db_status = "CONNECTING"
        except APIError as exc:
            stored_settings["last_qr_refresh_error"] = {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }

    if db_status == "CONNECTED":
        qr = None
        stored_settings.pop("last_qr", None)
        stored_settings.pop("last_qr_refresh_error", None)
    elif qr is not None:
        db_status = "CONNECTING"
        stored_settings["last_qr"] = qr

    stored_settings["last_status"] = result
    await _persist_integration_state(
        session,
        status=db_status,
        settings_data=stored_settings,
    )
    await session.commit()
    return success(
        {
            "product": PUBLIC_PRODUCT_NAME,
            "instance_name": instance_name,
            "status": db_status,
            "qr": qr,
            "phone": stored_settings.get("connected_phone"),
            "connection_method": stored_settings.get("connection_method"),
            "provider": {"ok": True},
        }
    )


@router.post("/reconnect")
async def reconnect(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    # Reconecta usando o fluxo histórico de QR. O pareamento é solicitado apenas
    # quando o operador explicitamente informa um telefone.
    return success(await _connect_response(session, context))


@router.post("/disconnect")
async def disconnect(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    instance_name, provider = await _tenant_provider(session, context)
    try:
        await provider.disconnect_instance()
    except APIError as exc:
        if _provider_status_code(exc) != 404:
            raise _public_provider_error("disconnect", exc) from exc
    stored_settings = await _stored_settings(session)
    stored_settings.pop("last_qr", None)
    await _persist_integration_state(
        session,
        status="DISCONNECTED",
        settings_data=stored_settings,
    )
    await session.commit()
    return success(
        {
            "product": PUBLIC_PRODUCT_NAME,
            "instance_name": instance_name,
            "status": "DISCONNECTED",
            "qr": None,
            "provider": {"ok": True},
        }
    )


@router.post("/send-text")
async def send_text(
    payload: SendTextRequest,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    phone = await _normalized_phone(session, payload.to)
    instance_name, provider = await _tenant_provider(session, context)
    try:
        result = await provider.send_text(phone, payload.message)
    except APIError as exc:
        raise _public_provider_error("send", exc) from exc
    return success(
        {
            "product": PUBLIC_PRODUCT_NAME,
            "instance_name": instance_name,
            "to": phone,
            "message": result,
        }
    )


@router.post("/test")
async def test_send(
    payload: TestSendRequest,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    normalized = await _normalized_phone(session, payload.phone)
    instance_name, provider = await _tenant_provider(session, context)
    try:
        result = await provider.send_text(normalized, payload.message)
    except APIError as exc:
        raise _public_provider_error("send", exc) from exc
    return success(
        {
            "product": PUBLIC_PRODUCT_NAME,
            "instance_name": instance_name,
            "to": normalized,
            "message": result,
            "test": True,
        }
    )


@router.post("/webhook/{integration_key}")
async def webhook(
    integration_key: str,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    payload = cast(dict[str, Any], await request.json())
    key_value = payload.get("key")
    key: dict[str, Any] = key_value if isinstance(key_value, dict) else {}
    provider_event_id = str(
        payload.get("id")
        or payload.get("event_id")
        or key.get("id")
        or request.headers.get("x-provider-event-id")
        or ""
    )
    if not provider_event_id:
        provider_event_id = f"missing-{integration_key}-{abs(hash(str(payload)))}"

    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    inserted = await session.scalar(
        text(
            """
            insert into whatsapp_events(
                provider_event_id, integration_key, payload
            )
            values(
                :provider_event_id, :integration_key, cast(:payload as jsonb)
            )
            on conflict(provider_event_id) do nothing
            returning id::text
            """
        ),
        {
            "provider_event_id": provider_event_id,
            "integration_key": integration_key,
            "payload": payload_json,
        },
    )
    if inserted:
        await session.execute(
            text(
                """
                insert into outbox_events(event_name, aggregate_id, payload)
                values(
                    'whatsapp.webhook.received',
                    :aggregate_id,
                    cast(:payload as jsonb)
                )
                """
            ),
            {
                "aggregate_id": inserted,
                "payload": json.dumps(
                    {
                        "integration_key": integration_key,
                        "provider_event_id": provider_event_id,
                    }
                ),
            },
        )
    await session.commit()

    if inserted:
        celery_app.send_task(
            "app.workers.tasks.process_whatsapp_webhook",
            args=[
                context.tenant_id,
                str(inserted),
                f"whatsapp-{inserted}",
            ],
            queue="whatsapp",
        )
    return success(
        {
            "product": PUBLIC_PRODUCT_NAME,
            "accepted": True,
            "duplicate": inserted is None,
            "queued": inserted is not None,
        }
    )
