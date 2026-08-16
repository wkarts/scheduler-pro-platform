from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import APIError


class WhatsAppProvider(ABC):
    @abstractmethod
    async def connect_instance(self) -> dict[str, Any]: ...

    @abstractmethod
    async def connection_status(self) -> dict[str, Any]: ...

    @abstractmethod
    async def send_text(self, to: str, message: str) -> dict[str, Any]: ...


class EvolutionWhatsAppProvider(WhatsAppProvider):
    def __init__(self) -> None:
        self.base_url = (settings.evolution_api_url or "").rstrip("/")
        self.token = settings.evolution_api_token or ""
        self.instance = settings.evolution_instance_name

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.token, "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.base_url or not self.token:
            raise APIError("EVOLUTION_NOT_CONFIGURED", "Evolution API não configurada.", 500)
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.request(method, f"{self.base_url}{path}", headers=self._headers(), json=payload)
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}
        if response.status_code >= 400:
            raise APIError("EVOLUTION_API_ERROR", "Falha na Evolution API.", 502, {"status_code": response.status_code, "response": data})
        return dict(data) if isinstance(data, dict) else {"data": data}

    async def connect_instance(self) -> dict[str, Any]:
        # Evolution v2 installations commonly expose connect and connectionState per instance.
        # Keeping the path centralized makes it easy to adjust if a deployment uses a compatible proxy.
        return await self._request("GET", f"/instance/connect/{self.instance}")

    async def connection_status(self) -> dict[str, Any]:
        return await self._request("GET", f"/instance/connectionState/{self.instance}")

    async def send_text(self, to: str, message: str) -> dict[str, Any]:
        payload = {"number": to, "text": message}
        return await self._request("POST", f"/message/sendText/{self.instance}", payload)


class WhatsAppProviderFactory:
    @staticmethod
    def make() -> WhatsAppProvider:
        return EvolutionWhatsAppProvider()
