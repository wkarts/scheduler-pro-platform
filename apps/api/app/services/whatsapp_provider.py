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
    async def connection_status(self) -> dict[str, Any]: ...

    @abstractmethod
    async def send_text(self, to: str, message: str) -> dict[str, Any]: ...


class EvolutionWhatsAppProvider(WhatsAppProvider):
    def __init__(self, instance_name: str | None = None) -> None:
        self.base_url = (settings.evolution_api_url or "").rstrip("/")
        self.token = settings.evolution_api_token or ""
        self.instance = (instance_name or settings.evolution_instance_name).strip()

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.token, "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.base_url or not self.token:
            raise APIError("EVOLUTION_NOT_CONFIGURED", "Evolution API não configurada.", 424)
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.request(method, f"{self.base_url}{path}", headers=self._headers(), json=payload)
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}
        if response.status_code >= 400:
            raise APIError(
                "EVOLUTION_API_ERROR",
                "Falha na Evolution API.",
                424,
                {"status_code": response.status_code, "response": data, "instance": self.instance, "path": path},
            )
        return dict(data) if isinstance(data, dict) else {"data": data}

    async def ensure_instance(self) -> dict[str, Any]:
        try:
            status = await self.connection_status()
            return {"created": False, "instance": self.instance, "status": status}
        except APIError as exc:
            status_code = int(exc.details.get("status_code", 0)) if isinstance(exc.details, dict) else 0
            if status_code != 404:
                raise
        created = await self._request(
            "POST",
            "/instance/create",
            {"instanceName": self.instance, "qrcode": True, "integration": "WHATSAPP-BAILEYS"},
        )
        return {"created": True, "instance": self.instance, "create": created}

    async def connect_instance(self) -> dict[str, Any]:
        ensured = await self.ensure_instance()
        connection = await self._request("GET", f"/instance/connect/{self.instance}")
        return {"instance": self.instance, "ensure": ensured, "connection": connection}

    async def connection_status(self) -> dict[str, Any]:
        return await self._request("GET", f"/instance/connectionState/{self.instance}")

    async def send_text(self, to: str, message: str) -> dict[str, Any]:
        payload = {"number": to, "textMessage": {"text": message}}
        return await self._request("POST", f"/message/sendText/{self.instance}", payload)


class WhatsAppProviderFactory:
    @staticmethod
    def make(instance_name: str | None = None) -> WhatsAppProvider:
        return EvolutionWhatsAppProvider(instance_name)
