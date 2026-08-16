from typing import Any, cast

import httpx

from app.core.errors import APIError


class CloudflareService:
    def __init__(
        self,
        api_token: str | None,
        zone_id: str | None,
        *,
        api_base_url: str = "https://api.cloudflare.com/client/v4",
        dry_run: bool = False,
        custom_hostname_origin: str | None = None,
    ) -> None:
        self.api_token = api_token
        self.zone_id = zone_id
        self.api_base_url = api_base_url.rstrip("/")
        self.dry_run = dry_run or not api_token or not zone_id
        self.custom_hostname_origin = custom_hostname_origin

    def _dry_result(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "dry_run": True, "action": action, "result": payload}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.dry_run:
            return self._dry_result(f"{method} {path}", payload or {})
        if not self.api_token:
            raise APIError("CLOUDFLARE_TOKEN_MISSING", "Token Cloudflare não configurado.", 500)
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method,
                f"{self.api_base_url}{path}",
                headers=headers,
                json=payload,
            )
        data = cast(dict[str, Any], response.json())
        if response.status_code >= 400 or not data.get("success", False):
            raise APIError(
                "CLOUDFLARE_API_ERROR",
                "Falha na integração Cloudflare.",
                502,
                {"status_code": response.status_code, "response": data},
            )
        return data

    def _zone_path(self, suffix: str) -> str:
        if not self.zone_id:
            raise APIError("CLOUDFLARE_ZONE_MISSING", "Zone ID Cloudflare não configurado.", 500)
        return f"/zones/{self.zone_id}{suffix}"

    async def create_dns_record(
        self,
        hostname: str,
        target: str,
        *,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict[str, Any]:
        payload = {
            "type": record_type,
            "name": hostname,
            "content": target,
            "proxied": proxied,
            "ttl": ttl,
        }
        return await self._request("POST", self._zone_path("/dns_records"), payload=payload)

    async def delete_dns_record(self, record_id: str) -> dict[str, Any]:
        return await self._request("DELETE", self._zone_path(f"/dns_records/{record_id}"))

    async def create_custom_hostname(self, hostname: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "hostname": hostname,
            "ssl": {"method": "http", "type": "dv", "settings": {"http2": "on"}},
        }
        if self.custom_hostname_origin:
            payload["custom_origin_server"] = self.custom_hostname_origin
        return await self._request("POST", self._zone_path("/custom_hostnames"), payload=payload)

    async def delete_custom_hostname(self, hostname_id: str) -> dict[str, Any]:
        return await self._request("DELETE", self._zone_path(f"/custom_hostnames/{hostname_id}"))

    async def get_custom_hostname_status(self, hostname_id: str) -> dict[str, Any]:
        return await self._request("GET", self._zone_path(f"/custom_hostnames/{hostname_id}"))

    async def request_validation(self, hostname: str) -> dict[str, Any]:
        return await self.create_custom_hostname(hostname)

    async def get_validation_status(self, hostname_id: str) -> dict[str, Any]:
        return await self.get_custom_hostname_status(hostname_id)

    async def purge_cache(self, hostname: str) -> dict[str, Any]:
        payload = {"hosts": [hostname]}
        return await self._request("POST", self._zone_path("/purge_cache"), payload=payload)
