from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import APIError


class WhatsAppProvider(ABC):
    @abstractmethod
    async def ensure_instance(self) -> dict[str, Any]: ...

    @abstractmethod
    async def connect_instance(self) -> dict[str, Any]: ...

    @abstractmethod
    async def connect_pairing(self, phone_number: str) -> dict[str, Any]: ...

    @abstractmethod
    async def connection_status(self) -> dict[str, Any]: ...

    @abstractmethod
    async def disconnect_instance(self) -> dict[str, Any]: ...

    @abstractmethod
    async def send_text(self, to: str, message: str) -> dict[str, Any]: ...


class EvolutionWhatsAppProvider(WhatsAppProvider):
    """Adapter privado da Evolution API.

    O nome do provider permanece interno. A interface pública pode usar uma
    nomenclatura neutra, mas conexão, sessão, QR, pareamento e envio continuam
    sendo executados diretamente pela Evolution API configurada no Scheduler Pro.
    """

    def __init__(self, instance_name: str | None = None) -> None:
        self.base_url = (settings.evolution_api_url or "").rstrip("/")
        self.token = settings.evolution_api_token or ""
        self.instance = (instance_name or settings.evolution_instance_name).strip()

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.token,
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.base_url or not self.token:
            raise APIError(
                "EVOLUTION_NOT_CONFIGURED",
                "Serviço de WhatsApp não configurado.",
                424,
            )
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(),
                json=payload,
                params=params,
            )
        try:
            data = response.json() if response.content else {"ok": True}
        except ValueError:
            data = {"raw": response.text[:4000]}
        if response.status_code >= 400:
            raise APIError(
                "EVOLUTION_API_ERROR",
                "Falha no serviço de WhatsApp.",
                424,
                {
                    "status_code": response.status_code,
                    "response": data,
                    "instance": self.instance,
                    "path": path,
                },
            )
        return dict(data) if isinstance(data, dict) else {"data": data}

    @staticmethod
    def _status_code(error: APIError) -> int:
        if not isinstance(error.details, dict):
            return 0
        try:
            return int(error.details.get("status_code") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _schema_rejection(error: APIError) -> bool:
        if EvolutionWhatsAppProvider._status_code(error) not in {400, 422}:
            return False
        details = error.details if isinstance(error.details, dict) else {}
        message = str(details.get("response") or "").casefold()
        return any(
            marker in message
            for marker in (
                "textmessage",
                "text message",
                "property text",
                "field text",
                "text is required",
            )
        )

    async def ensure_instance(self) -> dict[str, Any]:
        try:
            status = await self.connection_status()
            return {"created": False, "instance": self.instance, "status": status}
        except APIError as exc:
            if self._status_code(exc) != 404:
                raise
        created = await self._request(
            "POST",
            "/instance/create",
            {
                "instanceName": self.instance,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS",
            },
        )
        return {"created": True, "instance": self.instance, "create": created}

    async def connect_instance(self) -> dict[str, Any]:
        ensured = await self.ensure_instance()
        connection = await self._request("GET", f"/instance/connect/{self.instance}")
        return {"instance": self.instance, "ensure": ensured, "connection": connection}

    async def connect_pairing(self, phone_number: str) -> dict[str, Any]:
        """Solicita pareamento preservando compatibilidade entre builds Evolution v2.

        O contrato utilizado pela Financial Platform envia `number` no endpoint
        /instance/connect/{instance}. Alguns builds antigos aceitam os parâmetros
        pairingCode/phoneNumber; esse formato fica somente como fallback após uma
        rejeição de schema, nunca como substituto do fluxo principal.
        """
        ensured = await self.ensure_instance()
        normalized = "".join(char for char in str(phone_number or "") if char.isdigit())
        if not normalized:
            raise APIError("PHONE_REQUIRED", "Informe o telefone para pareamento.", 422)
        try:
            connection = await self._request(
                "GET",
                f"/instance/connect/{self.instance}",
                params={"number": normalized},
            )
        except APIError as exc:
            if self._status_code(exc) not in {400, 422}:
                raise
            connection = await self._request(
                "GET",
                f"/instance/connect/{self.instance}",
                params={"pairingCode": "true", "phoneNumber": normalized},
            )
        return {"instance": self.instance, "ensure": ensured, "connection": connection}

    async def connection_status(self) -> dict[str, Any]:
        return await self._request("GET", f"/instance/connectionState/{self.instance}")

    async def disconnect_instance(self) -> dict[str, Any]:
        return await self._request("DELETE", f"/instance/logout/{self.instance}")

    async def send_text(self, to: str, message: str) -> dict[str, Any]:
        """Mantém o payload histórico do Scheduler e aceita o schema moderno.

        O fallback só ocorre quando a Evolution rejeita explicitamente o schema
        antes do envio. Timeouts/5xx não são repetidos para evitar duplicidade.
        """
        path = f"/message/sendText/{self.instance}"
        compatible = {"number": to, "textMessage": {"text": message}}
        try:
            return await self._request("POST", path, compatible)
        except APIError as exc:
            if not self._schema_rejection(exc):
                raise
            modern = {"number": to, "text": message}
            return await self._request("POST", path, modern)


class WhatsAppProviderFactory:
    @staticmethod
    def make(instance_name: str | None = None) -> WhatsAppProvider:
        # Evolution continua sendo o provider real e único por trás da camada
        # visual neutra do Scheduler Pro.
        return EvolutionWhatsAppProvider(instance_name)
