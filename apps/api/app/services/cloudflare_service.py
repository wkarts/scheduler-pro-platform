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
        zone_name_hint: str | None = None,
    ) -> None:
        self.api_token = api_token
        self.configured_zone_id = (zone_id or "").strip() or None
        self.zone_id = self.configured_zone_id
        self.api_base_url = api_base_url.rstrip("/")
        self.zone_name_hint = (
            zone_name_hint or custom_hostname_origin or ""
        ).strip().lower().rstrip(".") or None
        self.dry_run = dry_run or not api_token or not (self.zone_id or self.zone_name_hint)
        self.custom_hostname_origin = custom_hostname_origin
        self._resolved_zone: dict[str, Any] | None = None

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

    @staticmethod
    def _zone_name_matches(zone_name: str, hint: str | None) -> bool:
        if not hint:
            return True
        clean_zone = zone_name.strip().lower().rstrip(".")
        clean_hint = hint.strip().lower().rstrip(".")
        return clean_hint == clean_zone or clean_hint.endswith(f".{clean_zone}")

    def _zone_candidates(self) -> list[str]:
        hint = self.zone_name_hint
        if not hint:
            return []
        labels = [label for label in hint.split(".") if label]
        candidates: list[str] = []
        for index in range(max(len(labels) - 1, 1)):
            candidate = ".".join(labels[index:])
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        return candidates

    async def resolve_zone(self) -> dict[str, Any]:
        if self.dry_run:
            return {
                "id": self.zone_id,
                "name": self.zone_name_hint,
                "configured_zone_id": self.configured_zone_id,
                "auto_resolved": False,
                "dry_run": True,
            }
        if self._resolved_zone is not None:
            return self._resolved_zone

        configured_error: dict[str, Any] | None = None
        if self.configured_zone_id:
            try:
                response = await self._request("GET", f"/zones/{self.configured_zone_id}")
                result = response.get("result")
                if isinstance(result, dict):
                    zone_name = str(result.get("name") or "")
                    if self._zone_name_matches(zone_name, self.zone_name_hint):
                        self.zone_id = str(result.get("id") or self.configured_zone_id)
                        self._resolved_zone = {
                            **result,
                            "configured_zone_id": self.configured_zone_id,
                            "auto_resolved": False,
                        }
                        return self._resolved_zone
                    configured_error = {
                        "code": "CLOUDFLARE_ZONE_NAME_MISMATCH",
                        "message": (
                            f"A Zone ID configurada pertence a {zone_name or 'outra zone'}, "
                            f"mas a plataforma usa {self.zone_name_hint}."
                        ),
                    }
            except APIError as exc:
                configured_error = {
                    "code": exc.code,
                    "message": exc.message,
                    "status_code": exc.status_code,
                    "details": exc.details,
                }

        discovery_errors: list[dict[str, Any]] = []
        for candidate in self._zone_candidates():
            try:
                response = await self._request(
                    "GET",
                    f"/zones?{urlencode({'name': candidate, 'status': 'active', 'per_page': '50'})}",
                )
            except APIError as exc:
                discovery_errors.append(
                    {
                        "candidate": candidate,
                        "code": exc.code,
                        "message": exc.message,
                        "status_code": exc.status_code,
                    }
                )
                continue
            result = response.get("result")
            if not isinstance(result, list):
                continue
            for zone in result:
                if not isinstance(zone, dict):
                    continue
                zone_id = str(zone.get("id") or "").strip()
                zone_name = str(zone.get("name") or "").strip().lower().rstrip(".")
                if not zone_id or not self._zone_name_matches(zone_name, self.zone_name_hint):
                    continue
                self.zone_id = zone_id
                self._resolved_zone = {
                    **zone,
                    "configured_zone_id": self.configured_zone_id,
                    "auto_resolved": zone_id != self.configured_zone_id,
                }
                return self._resolved_zone

        raise APIError(
            "CLOUDFLARE_ZONE_RESOLUTION_ERROR",
            "Não foi possível resolver a Zone Cloudflare da plataforma.",
            424,
            {
                "configured_zone_id": self.configured_zone_id,
                "zone_name_hint": self.zone_name_hint,
                "configured_zone_error": configured_error,
                "discovery_errors": discovery_errors,
                "hint": (
                    "Use o Zone ID da zone DNS, nunca o Account ID. O backend também pode "
                    "autodetectar a zone quando o token possui Zone:Read."
                ),
            },
        )

    async def verify_token(self) -> dict[str, Any]:
        if self.dry_run:
            return self._dry_result(
                "VERIFY CLOUDFLARE",
                {"zone_id": self.zone_id, "zone_name_hint": self.zone_name_hint},
            )

        token_error: APIError | None = None
        token_verification: dict[str, Any] | None = None
        try:
            token_verification = await self._request("GET", "/user/tokens/verify")
        except APIError as exc:
            if exc.code != "CLOUDFLARE_AUTH_ERROR":
                raise
            token_error = exc

        try:
            zone = await self.resolve_zone()
        except APIError:
            if token_error is not None:
                raise token_error
            raise

        result: dict[str, Any] = {
            "success": True,
            "verification_mode": "token_and_zone_access",
            "result": zone,
            "configured_zone_id": self.configured_zone_id,
            "resolved_zone_id": self.zone_id,
            "zone_name": zone.get("name"),
            "auto_resolved_zone": bool(zone.get("auto_resolved")),
        }
        if token_verification is not None:
            result["token"] = token_verification.get("result")
        if token_error is not None:
            result["warning"] = (
                "O endpoint /user/tokens/verify não aceitou a credencial, mas o token possui "
                "acesso real à zone resolvida."
            )
            result["token_verify_error"] = {
                "code": token_error.code,
                "message": token_error.message,
                "details": token_error.details,
            }
        return result

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
        try:
            data = cast(dict[str, Any], response.json())
        except ValueError as exc:
            raise APIError(
                "CLOUDFLARE_INVALID_RESPONSE",
                "A Cloudflare retornou uma resposta inválida.",
                424,
                {"status_code": response.status_code, "body": response.text[:2000]},
            ) from exc
        if response.status_code >= 400 or not data.get("success", False):
            cf_code = self._cloudflare_error_code(data)
            if "/purge_cache" in path and response.status_code in {401, 403}:
                raise APIError(
                    "CLOUDFLARE_CACHE_PURGE_PERMISSION_ERROR",
                    "Token Cloudflare ativo, mas sem permissão para purge de cache nesta zone.",
                    424,
                    {
                        "status_code": response.status_code,
                        "response": data,
                        "hint": (
                            "Adicione ao token a permissão Cache Purge para a zone configurada, "
                            "além de Zone:Read e DNS:Edit."
                        ),
                    },
                )
            if response.status_code in {401, 403} or cf_code == 10000:
                raise APIError(
                    "CLOUDFLARE_AUTH_ERROR",
                    "A credencial Cloudflare não possui acesso à operação solicitada.",
                    424,
                    {
                        "status_code": response.status_code,
                        "response": data,
                        "hint": (
                            "Confira a Zone ID e as permissões específicas da operação. DNS, "
                            "Custom Hostnames e Cache Purge possuem permissões distintas."
                        ),
                    },
                )
            raise APIError(
                "CLOUDFLARE_API_ERROR",
                "Falha na integração Cloudflare.",
                424,
                {"status_code": response.status_code, "response": data},
            )
        return data

    async def _zone_path(self, suffix: str) -> str:
        zone = await self.resolve_zone()
        zone_id = str(zone.get("id") or self.zone_id or "").strip()
        if not zone_id:
            raise APIError(
                "CLOUDFLARE_ZONE_MISSING",
                "Zone ID Cloudflare não configurado ou resolvido.",
                424,
            )
        return f"/zones/{zone_id}{suffix}"

    async def list_dns_records(
        self,
        hostname: str,
        record_type: str | None = None,
    ) -> dict[str, Any]:
        if self.dry_run:
            return self._dry_result(
                "GET /dns_records",
                {"records": [], "name": hostname},
            )
        params: dict[str, str] = {"name": hostname.strip().lower().rstrip(".")}
        if record_type:
            params["type"] = record_type.upper()
        path = await self._zone_path("/dns_records")
        return await self._request("GET", f"{path}?{urlencode(params)}")

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
            "content": (
                target.strip().lower().rstrip(".")
                if record_type.upper() == "CNAME"
                else target.strip()
            ),
            "proxied": proxied,
            "ttl": ttl,
        }
        return await self._request(
            "POST",
            await self._zone_path("/dns_records"),
            payload=payload,
        )

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
        clean_target = (
            target.strip().lower().rstrip(".")
            if record_type.upper() == "CNAME"
            else target.strip()
        )
        existing = await self.list_dns_records(clean_hostname, record_type)
        records: list[Any] = []
        existing_result = existing.get("result")
        if isinstance(existing_result, list):
            records = existing_result
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
            created = await self.create_dns_record(
                clean_hostname,
                clean_target,
                record_type=record_type,
                proxied=proxied,
                ttl=ttl,
            )
            return {
                "success": True,
                "existing": False,
                "record_exists": True,
                "result": created.get("result"),
                "cloudflare": created,
            }
        except APIError:
            after_error = await self.list_dns_records(clean_hostname, record_type)
            retry_records: list[Any] = []
            retry_result = after_error.get("result")
            if isinstance(retry_result, list):
                retry_records = retry_result
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
        return await self._request(
            "DELETE",
            await self._zone_path(f"/dns_records/{record_id}"),
        )

    async def create_custom_hostname(self, hostname: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "hostname": hostname,
            "ssl": {
                "method": "http",
                "type": "dv",
                "settings": {"http2": "on"},
            },
        }
        if self.custom_hostname_origin:
            payload["custom_origin_server"] = self.custom_hostname_origin
        return await self._request(
            "POST",
            await self._zone_path("/custom_hostnames"),
            payload=payload,
        )

    async def delete_custom_hostname(self, hostname_id: str) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            await self._zone_path(f"/custom_hostnames/{hostname_id}"),
        )

    async def get_custom_hostname_status(self, hostname_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            await self._zone_path(f"/custom_hostnames/{hostname_id}"),
        )

    async def request_validation(self, hostname: str) -> dict[str, Any]:
        return await self.create_custom_hostname(hostname)

    async def get_validation_status(self, hostname_id: str) -> dict[str, Any]:
        return await self.get_custom_hostname_status(hostname_id)

    async def purge_cache(self, hostname: str) -> dict[str, Any]:
        payload = {"hosts": [hostname]}
        return await self._request(
            "POST",
            await self._zone_path("/purge_cache"),
            payload=payload,
        )
