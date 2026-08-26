from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIError
from app.core.tenant_context import TenantContext
from app.services.phone_normalization import PhoneNormalizationService
from app.services.whatsapp_provider import WhatsAppProvider, WhatsAppProviderFactory


FRIENDLY_STATUS = {
    "DISCONNECTED": "Desconectado",
    "CONNECTING": "Conectando",
    "WAITING_QR": "Aguardando leitura do QR Code",
    "WAITING_PAIRING_CODE": "Aguardando código de pareamento",
    "WAITING_CONFIRMATION": "Aguardando confirmação",
    "CONNECTED": "Conectado",
    "RECONNECTING": "Reconectando",
    "FAILED": "Falha",
}


class ARGWSWhatsAppService:
    """Fachada pública da integração de comunicação do Scheduler Pro.

    Nenhum detalhe do conector interno é devolvido ao consumidor. Payloads brutos
    podem ser persistidos apenas em metadata administrativa protegida para
    diagnóstico, sem aparecer na interface da empresa.
    """

    def __init__(
        self,
        session: AsyncSession,
        context: TenantContext,
    ) -> None:
        self.session = session
        self.context = context
        self._phone: PhoneNormalizationService | None = None

    async def _phone_service(self) -> PhoneNormalizationService:
        if self._phone is None:
            self._phone = await PhoneNormalizationService.from_session(self.session)
        return self._phone

    async def _provider(self) -> tuple[str, WhatsAppProvider]:
        instance_name = await self.session.scalar(
            text(
                "select instance_name from whatsapp_integrations "
                "where name='default' limit 1"
            )
        )
        if not instance_name:
            instance_name = f"{settings.evolution_instance_name}-{self.context.slug}"[:160]
            await self.session.execute(
                text(
                    """
                    insert into whatsapp_integrations(
                        name, provider, instance_name, status, settings
                    ) values(
                        'default', 'evolution', :instance_name,
                        'DISCONNECTED', '{}'::jsonb
                    )
                    on conflict(name) do update
                    set instance_name=excluded.instance_name
                    """
                ),
                {"instance_name": instance_name},
            )
            await self.session.commit()
        return str(instance_name), WhatsAppProviderFactory.make(str(instance_name))

    async def _integration(self) -> tuple[str, dict[str, Any]]:
        row = (
            await self.session.execute(
                text(
                    """
                    select status, settings
                    from whatsapp_integrations
                    where name='default'
                    limit 1
                    """
                )
            )
        ).mappings().first()
        status = str(row["status"] if row else "DISCONNECTED").upper()
        data = dict(row["settings"]) if row and isinstance(row["settings"], dict) else {}
        return status, data

    async def _persist(
        self,
        status: str,
        data: dict[str, Any],
        *,
        commit: bool = True,
    ) -> None:
        data["updated_at"] = datetime.now(UTC).isoformat()
        await self.session.execute(
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
                "settings": json.dumps(data, ensure_ascii=False, default=str),
            },
        )
        if commit:
            await self.session.commit()

    @staticmethod
    def _walk(value: object) -> list[object]:
        found: list[object] = [value]
        if isinstance(value, dict):
            for nested in value.values():
                found.extend(ARGWSWhatsAppService._walk(nested))
        elif isinstance(value, list):
            for nested in value:
                found.extend(ARGWSWhatsAppService._walk(nested))
        return found

    @staticmethod
    def _image_data_uri(value: object) -> str | None:
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

    @classmethod
    def _qr(cls, payload: object) -> dict[str, Any] | None:
        for candidate in cls._walk(payload):
            if not isinstance(candidate, dict):
                continue
            image = None
            for key in ("base64", "qrcode", "qrCode", "qr"):
                image = cls._image_data_uri(candidate.get(key))
                if image:
                    break
            raw_code = candidate.get("code")
            if image is None:
                image = cls._image_data_uri(raw_code)
            if image:
                return {
                    "image": image,
                    "refresh_available": True,
                }
        return None

    @classmethod
    def _pairing_code(cls, payload: object) -> str | None:
        for candidate in cls._walk(payload):
            if not isinstance(candidate, dict):
                continue
            value = candidate.get("pairingCode") or candidate.get("pairing_code")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @classmethod
    def _raw_state(cls, payload: object) -> str:
        for candidate in cls._walk(payload):
            if not isinstance(candidate, dict):
                continue
            for key in ("state", "status", "connectionStatus"):
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().lower()
        return "unknown"

    @staticmethod
    def _public_status(status: str) -> dict[str, str]:
        normalized = status if status in FRIENDLY_STATUS else "FAILED"
        return {"code": normalized, "label": FRIENDLY_STATUS[normalized]}

    @staticmethod
    def _internal_error(exc: APIError) -> dict[str, Any]:
        # Somente para storage administrativo interno. A resposta externa nunca
        # recebe `details` do conector.
        return {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _public_error(action: str, exc: APIError) -> APIError:
        status_code = 503 if exc.status_code >= 500 or exc.status_code == 424 else exc.status_code
        messages = {
            "connect": "Não foi possível iniciar a conexão com o WhatsApp. Tente novamente.",
            "pair": "Não foi possível gerar o código de pareamento. Confira o telefone e tente novamente.",
            "status": "Não foi possível verificar a conexão com o WhatsApp.",
            "disconnect": "Não foi possível desconectar o WhatsApp. Tente novamente.",
            "send": "Não foi possível enviar a mensagem pelo WhatsApp.",
        }
        return APIError(
            f"ARGWS_WHATSAPP_{action.upper()}_FAILED",
            messages.get(action, "Não foi possível concluir a operação no WhatsApp."),
            status_code,
        )

    async def connect_qr(self) -> dict[str, Any]:
        _, provider = await self._provider()
        _, stored = await self._integration()
        try:
            result = await provider.connect_instance()
        except APIError as exc:
            stored["last_internal_error"] = self._internal_error(exc)
            await self._persist("FAILED", stored)
            raise self._public_error("connect", exc) from exc
        qr = self._qr(result)
        stored["last_connect_internal"] = result
        stored["connection_method"] = "QR_CODE"
        stored.pop("last_internal_error", None)
        if qr:
            stored["last_qr"] = qr
            status = "WAITING_QR"
        else:
            status = "WAITING_CONFIRMATION"
        await self._persist(status, stored)
        return {
            "product": "ARGWS WhatsApp API",
            "status": self._public_status(status),
            "connection_method": "QR_CODE",
            "qr_code": qr,
        }

    async def connect_pairing(self, raw_phone: str) -> dict[str, Any]:
        phone_service = await self._phone_service()
        phone = phone_service.normalize(raw_phone, required=True)
        assert phone is not None
        _, provider = await self._provider()
        _, stored = await self._integration()
        try:
            result = await provider.connect_pairing(phone)
        except APIError as exc:
            stored["last_internal_error"] = self._internal_error(exc)
            await self._persist("FAILED", stored)
            raise self._public_error("pair", exc) from exc
        code = self._pairing_code(result)
        stored["last_pairing_internal"] = result
        stored["connection_method"] = "PAIRING_CODE"
        stored["connected_phone"] = phone
        stored.pop("last_internal_error", None)
        status = "WAITING_PAIRING_CODE" if code else "WAITING_CONFIRMATION"
        await self._persist(status, stored)
        if not code:
            raise APIError(
                "ARGWS_WHATSAPP_PAIRING_CODE_UNAVAILABLE",
                "O código de pareamento ainda não ficou disponível. Tente gerar novamente.",
                409,
            )
        return {
            "product": "ARGWS WhatsApp API",
            "status": self._public_status(status),
            "connection_method": "PAIRING_CODE",
            "phone": phone,
            "pairing_code": code,
        }

    async def status(self) -> dict[str, Any]:
        _, provider = await self._provider()
        previous_status, stored = await self._integration()
        try:
            result = await provider.connection_status()
        except APIError as exc:
            # Instância ausente equivale a desconectado; outros erros são falha
            # de diagnóstico sem exposição do conector.
            raw_status = int(exc.details.get("status_code", 0)) if isinstance(exc.details, dict) else 0
            if raw_status == 404:
                result = {"state": "disconnected"}
            else:
                stored["last_internal_error"] = self._internal_error(exc)
                await self._persist("FAILED", stored)
                raise self._public_error("status", exc) from exc

        raw_state = self._raw_state(result)
        if raw_state in {"open", "connected", "online"}:
            status = "CONNECTED"
        elif raw_state in {"close", "closed", "disconnected", "offline", "missing"}:
            status = "DISCONNECTED"
        elif previous_status in {"WAITING_QR", "WAITING_PAIRING_CODE", "RECONNECTING"}:
            status = previous_status
        else:
            status = "CONNECTING"

        qr = None
        if status == "WAITING_QR":
            qr = stored.get("last_qr") if isinstance(stored.get("last_qr"), dict) else None
        if status == "CONNECTED":
            stored.pop("last_qr", None)
            stored.pop("last_internal_error", None)
        stored["last_status_internal"] = result
        await self._persist(status, stored)
        return {
            "product": "ARGWS WhatsApp API",
            "status": self._public_status(status),
            "connection_method": stored.get("connection_method"),
            "phone": stored.get("connected_phone"),
            "last_activity": stored.get("updated_at"),
            "qr_code": qr,
        }

    async def disconnect(self) -> dict[str, Any]:
        _, provider = await self._provider()
        _, stored = await self._integration()
        try:
            result = await provider.disconnect_instance()
        except APIError as exc:
            raw_status = int(exc.details.get("status_code", 0)) if isinstance(exc.details, dict) else 0
            if raw_status != 404:
                stored["last_internal_error"] = self._internal_error(exc)
                await self._persist("FAILED", stored)
                raise self._public_error("disconnect", exc) from exc
            result = {"already_disconnected": True}
        stored["last_disconnect_internal"] = result
        stored.pop("last_qr", None)
        stored.pop("last_internal_error", None)
        await self._persist("DISCONNECTED", stored)
        return {
            "product": "ARGWS WhatsApp API",
            "status": self._public_status("DISCONNECTED"),
        }

    async def reconnect(self) -> dict[str, Any]:
        _, stored = await self._integration()
        await self._persist("RECONNECTING", stored)
        method = str(stored.get("connection_method") or "QR_CODE")
        phone = str(stored.get("connected_phone") or "")
        if method == "PAIRING_CODE" and phone:
            return await self.connect_pairing(phone)
        return await self.connect_qr()

    async def send_text(self, raw_to: str, message: str) -> dict[str, Any]:
        phone_service = await self._phone_service()
        to = phone_service.normalize(raw_to, required=True)
        assert to is not None
        _, provider = await self._provider()
        _, stored = await self._integration()
        try:
            result = await provider.send_text(to, message)
        except APIError as exc:
            stored["last_internal_error"] = self._internal_error(exc)
            await self._persist("FAILED", stored)
            raise self._public_error("send", exc) from exc
        stored["last_send_internal"] = result
        stored["last_message_at"] = datetime.now(UTC).isoformat()
        stored.pop("last_internal_error", None)
        await self._persist(str((await self._integration())[0]), stored)
        return {
            "product": "ARGWS WhatsApp API",
            "accepted": True,
            "to": to,
        }
