import json
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_context, get_tenant_session
from app.core.responses import success
from app.core.tenant_context import TenantContext
from app.services.argws_whatsapp_service import ARGWSWhatsAppService
from app.workers.celery_app import celery_app

router = APIRouter()


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
    """Compatibilidade interna para formatos históricos de QR.

    A função não faz parte do contrato público da ARGWS WhatsApp API; existe
    somente para manter testes e consumidores internos antigos funcionando.
    """
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
    """Normaliza variantes internas sem expor payload técnico ao cliente."""
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


def _service(
    session: AsyncSession,
    context: TenantContext,
) -> ARGWSWhatsAppService:
    return ARGWSWhatsAppService(session, context)


@router.post("/connect")
async def connect_legacy_qr(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Alias compatível para clientes anteriores: equivale à conexão por QR."""
    return success(await _service(session, context).connect_qr())


@router.post("/connect/qr")
async def connect_qr(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    return success(await _service(session, context).connect_qr())


@router.post("/connect/pairing")
async def connect_pairing(
    payload: PairingRequest,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    return success(await _service(session, context).connect_pairing(payload.phone))


@router.get("/status")
async def status(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    return success(await _service(session, context).status())


@router.post("/reconnect")
async def reconnect(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    return success(await _service(session, context).reconnect())


@router.post("/disconnect")
async def disconnect(
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    return success(await _service(session, context).disconnect())


@router.post("/send-text")
async def send_text(
    payload: SendTextRequest,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    return success(await _service(session, context).send_text(payload.to, payload.message))


@router.post("/test")
async def test_send(
    payload: TestSendRequest,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    result = await _service(session, context).send_text(payload.phone, payload.message)
    return success({**result, "test": True})


@router.post("/webhook/{integration_key}")
async def webhook(
    integration_key: str,
    request: Request,
    session: AsyncSession = Depends(get_tenant_session),
    context: TenantContext = Depends(get_tenant_context),
) -> dict[str, Any]:
    """Preserva o pipeline idempotente já existente.

    O payload bruto permanece somente na trilha interna da empresa e nunca é
    refletido de volta ao cliente. O nome público da integração é estável.
    """
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
            "product": "ARGWS WhatsApp API",
            "accepted": True,
            "duplicate": inserted is None,
            "queued": inserted is not None,
        }
    )
