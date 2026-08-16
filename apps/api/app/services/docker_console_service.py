import hmac
import os
from hashlib import sha256
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import APIError


class DockerConsoleService:
    def __init__(self) -> None:
        self.base_url = os.getenv("LOG_AGENT_URL", "http://scheduler-log-agent:8090").rstrip("/")
        self.enabled = os.getenv("LOG_AGENT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

    def _token(self) -> str:
        return hmac.new(settings.app_secret_key.encode(), b"scheduler-pro-log-agent", sha256).hexdigest()

    def _headers(self) -> dict[str, str]:
        return {"X-Log-Agent-Token": self._token()}

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            raise APIError("DOCKER_CONSOLE_DISABLED", "Console Docker não está habilitado neste ambiente.", 503)
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=25.0) as client:
                response = await client.get(path, params=params, headers=self._headers())
        except httpx.HTTPError as exc:
            raise APIError("DOCKER_CONSOLE_UNAVAILABLE", "Agente de logs Docker indisponível.", 503, {"error": str(exc)}) from exc
        if response.status_code == 404:
            raise APIError("DOCKER_CONTAINER_NOT_FOUND", "Container não encontrado no projeto Scheduler Pro.", 404)
        if response.status_code >= 400:
            raise APIError("DOCKER_CONSOLE_ERROR", "Falha ao consultar console Docker.", 502, {"status_code": response.status_code, "body": response.text[:1000]})
        payload = response.json()
        if not isinstance(payload, dict):
            raise APIError("DOCKER_CONSOLE_PROTOCOL", "Resposta inválida do agente Docker.", 502)
        return payload

    async def health(self) -> dict[str, Any]:
        return await self._get("/health")

    async def containers(self) -> list[dict[str, Any]]:
        payload = await self._get("/containers")
        rows = payload.get("containers", [])
        return rows if isinstance(rows, list) else []

    async def logs(self, container: str, *, tail: int = 500, since: int | None = None, search: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"container": container, "tail": tail}
        if since is not None:
            params["since"] = since
        if search:
            params["search"] = search
        return await self._get("/logs", params)
