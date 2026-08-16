from typing import Any, cast
from urllib.parse import urlencode

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

    @staticmethod
    def _cloudflare_error_code(data: dict[str, Any]) -> int | None:
        errors = data.get("errors")
        if not isinstance(errors, list) or not errors:
            return None
        first = errors[0]
        if not isinstance(first, dict):
            return None
        code = first.get("code")
        return int(code) if isinstance(code, int) else None

    async def verify_token(self) -> dict[str, Any]:
        return await self._request("GET", "/user/tokens/verify")

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
            raise APIError(
                "CLOUDFLARE_TOKEN_MISSING",
                "Token Cloudflare não configurado.",
                424,
                {"hint": "Configure CLOUDFLARE_API_TOKEN no .env do CloudPanel/Dockge."},
            )
        headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, f"{self.api_base_url}{path}", headers=headers, json=payload)
        data = cast(dict[str, Any], response.json())
        if response.status_code >= 400 or not data.get("success", False):
            cf_code = self._cloudflare_error_code(data)
            if response.status_code in {401, 403} or cf_code == 10000:
                raise APIError(
                    "CLOUDFLARE_AUTH_ERROR",
                    "Token Cloudflare inválido, expirado, revogado ou sem acesso à Zone ID configurada.",
                    424,
                    {
                        "status_code": response.status_code,
                        "response": data,
                        "hint": "Verifique /user/tokens/verify, confirme a zone do domínio e permissões Zone:DNS:Edit.",
                    },
                )
            raise APIError(
                "CLOUDFLARE_API_ERROR",
                "Falha na integração Cloudflare.",
                424,
                {"status_code": response.status_code, "response": data},
            )
        return data

    def _zone_path(self, suffix: str) -> str:
        if not self.zone_id:
            raise APIError("CLOUDFLARE_ZONE_MISSING", "Zone ID Cloudflare não configurado.", 424)
        return f"/zones/{self.zone_id}{suffix}"

    async def list_dns_records(self, hostname: str, record_type: str | None = None) -> dict[str, Any]:
        if self.dry_run:
            return self._dry_result("GET /dns_records", {"records": [], "name": hostname})
        params: dict[str, str] = {"name": hostname.strip().lower().rstrip(".")}
        if record_type:
            params["type"] = record_type.upper()
        return await self._request("GET", f"{self._zone_path('/dns_records')}?{urlencode(params)}")

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
            "name": hostname.strip().lower().rstrip("."),
            "content": target.strip().lower().rstrip(".") if record_type.upper() == "CNAME" else target.strip(),
            "proxied": proxied,
            "ttl": ttl,
        }
        return await self._request("POST", self._zone_path("/dns_records"), payload=payload)

    async def ensure_dns_record(
        self,
        hostname: str,
        target: str,
        *,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict[str, Any]:
        clean_hostname = hostname.strip().lower().rstrip(".")
        clean_target = target.strip().lower().rstrip(".") if record_type.upper() == "CNAME" else target.strip()
        existing = await self.list_dns_records(clean_hostname, record_type)
        records = existing.get("result") if isinstance(existing.get("result"), list) else []
        for record in records:
            if not isinstance(record, dict):
                continue
            content = str(record.get("content", "")).strip().lower().rstrip(".")
            if content == clean_target:
                return {
                    "success": True,
                    "existing": True,
                    "record_exists": True,
                    "result": record,
                    "lookup": existing,
                }
        try:
            created = await self.create_dns_record(clean_hostname, clean_target, record_type=record_type, proxied=proxied, ttl=ttl)
            return {"success": True, "existing": False, "record_exists": True, "result": created.get("result"), "cloudflare": created}
        except APIError:
            after_error = await self.list_dns_records(clean_hostname, record_type)
            retry_records = after_error.get("result") if isinstance(after_error.get("result"), list) else []
            if retry_records:
                return {
                    "success": True,
                    "existing": True,
                    "record_exists": True,
                    "result": retry_records[0],
                    "lookup": after_error,
                    "recovered_after_create_error": True,
                }
            raise

    async def delete_dns_record(self, record_id: str) -> dict[str, Any]:
        return await self._request("DELETE", self._zone_path(f"/dns_records/{record_id}"))

    async def create_custom_hostname(self, hostname: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"hostname": hostname, "ssl": {"method": "http", "type": "dv", "settings": {"http2": "on"}}}
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
