from typing import Any, cast
from urllib.parse import urlencode

import httpx

from app.core.errors import APIError


class CloudflareService:
    """Cliente Cloudflare com reconciliação idempotente de zone, DNS e SSL SaaS."""

    def __init__(
        self,
        api_token: str | None,
        zone_id: str | None,
        *,
        api_base_url: str = "https://api.cloudflare.com/client/v4",
        dry_run: bool = False,
        custom_hostname_origin: str | None = None,
        zone_name_hint: str | None = None,
        custom_hostname_ca: str = "lets_encrypt",
    ) -> None:
        self.api_token = (api_token or "").strip() or None
        self.configured_zone_id = (zone_id or "").strip() or None
        self.zone_id = self.configured_zone_id
        self.api_base_url = api_base_url.rstrip("/")
        self.custom_hostname_origin = (
            (custom_hostname_origin or "").strip().lower().rstrip(".") or None
        )
        self.explicit_zone_name = (
            (zone_name_hint or "").strip().lower().rstrip(".") or None
        )
        self.zone_name_hint = self.explicit_zone_name or self.custom_hostname_origin
        self.custom_hostname_ca = custom_hostname_ca.strip().lower() or "lets_encrypt"
        self.dry_run = bool(dry_run)
        self._resolved_zone: dict[str, Any] | None = None

    def _dry_result(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "dry_run": True, "action": action, "result": payload}

    @staticmethod
    def _clean_hostname(value: str) -> str:
        return value.strip().lower().rstrip(".")

    @classmethod
    def _clean_content(cls, value: str, record_type: str) -> str:
        clean = value.strip()
        return cls._clean_hostname(clean) if record_type.upper() == "CNAME" else clean

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
        if self.explicit_zone_name:
            return [self.explicit_zone_name]
        labels = [label for label in hint.split(".") if label]
        candidates: list[str] = []
        # Ex.: proxy.scheduler.argws.com.br -> proxy..., scheduler... e argws.com.br.
        # Os dois últimos rótulos isolados nunca são consultados, evitando com.br.
        stop = max(len(labels) - 2, 1)
        for index in range(stop):
            candidate = ".".join(labels[index:])
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        return candidates

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
                {"hint": "Configure CLOUDFLARE_API_TOKEN; dry-run nunca é ativado implicitamente."},
            )

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    f"{self.api_base_url}{path}",
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError as exc:
            raise APIError(
                "CLOUDFLARE_NETWORK_ERROR",
                "Não foi possível conectar à API Cloudflare.",
                424,
                {"operation": f"{method} {path}", "exception": exc.__class__.__name__},
            ) from exc

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
            details = {
                "status_code": response.status_code,
                "response": data,
                "operation": f"{method} {path}",
            }
            if response.status_code == 401 or cf_code == 10000:
                raise APIError(
                    "CLOUDFLARE_AUTH_ERROR",
                    "A Cloudflare rejeitou a credencial enviada.",
                    424,
                    {
                        **details,
                        "hint": (
                            "Revogue tokens expostos, gere um novo API Token e confirme o header "
                            "Bearer. O código 10000/HTTP 401 é autenticação, não falta de Cache Purge."
                        ),
                    },
                )
            if "/purge_cache" in path and response.status_code == 403:
                raise APIError(
                    "CLOUDFLARE_CACHE_PURGE_PERMISSION_ERROR",
                    "O token autenticou, mas não possui Cache Purge nesta zone.",
                    424,
                    {
                        **details,
                        "hint": "Adicione Cache Purge à zone, além de Zone:Read e DNS:Edit.",
                    },
                )
            if response.status_code == 403:
                raise APIError(
                    "CLOUDFLARE_PERMISSION_ERROR",
                    "O token autenticou, mas não possui permissão para esta operação.",
                    424,
                    {
                        **details,
                        "hint": (
                            "DNS usa Zone DNS Edit; Custom Hostnames usa SSL and Certificates "
                            "Read/Write; leitura da zone usa Zone Read."
                        ),
                    },
                )
            raise APIError(
                "CLOUDFLARE_API_ERROR",
                "Falha na integração Cloudflare.",
                424,
                details,
            )
        return data

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
                    matches_hint = (
                        self._clean_hostname(zone_name) == self.explicit_zone_name
                        if self.explicit_zone_name
                        else self._zone_name_matches(zone_name, self.zone_name_hint)
                    )
                    if matches_hint:
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
                zone_name = self._clean_hostname(str(zone.get("name") or ""))
                matches_hint = (
                    zone_name == self.explicit_zone_name
                    if self.explicit_zone_name
                    else self._zone_name_matches(zone_name, self.zone_name_hint)
                )
                if not zone_id or not matches_hint:
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
                    "Configure CLOUDFLARE_ZONE_NAME (ex.: argws.com.br) ou o Zone ID DNS. "
                    "Nunca use o Account ID como Zone ID."
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
                "O endpoint de verificação recusou a credencial, porém a zone respondeu. "
                "Revise a credencial antes de considerar a integração saudável."
            )
            result["token_verify_error"] = {
                "code": token_error.code,
                "message": token_error.message,
                "details": token_error.details,
            }
        return result

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
        clean_hostname = self._clean_hostname(hostname)
        if self.dry_run:
            return self._dry_result("GET /dns_records", {"records": [], "name": clean_hostname})
        params: dict[str, str] = {"name": clean_hostname, "per_page": "100"}
        if record_type:
            params["type"] = record_type.upper()
        path = await self._zone_path("/dns_records")
        return await self._request("GET", f"{path}?{urlencode(params)}")

    @classmethod
    def _dns_payload(
        cls,
        hostname: str,
        target: str,
        *,
        record_type: str,
        proxied: bool,
        ttl: int,
    ) -> dict[str, Any]:
        normalized_type = record_type.upper()
        return {
            "type": normalized_type,
            "name": cls._clean_hostname(hostname),
            "content": cls._clean_content(target, normalized_type),
            "proxied": bool(proxied),
            "ttl": int(ttl),
        }

    @classmethod
    def _dns_record_matches(cls, record: dict[str, Any], desired: dict[str, Any]) -> bool:
        record_type = str(record.get("type") or "").upper()
        record_name = cls._clean_hostname(str(record.get("name") or ""))
        record_content = cls._clean_content(str(record.get("content") or ""), record_type)
        return (
            record_type == desired["type"]
            and record_name == desired["name"]
            and record_content == desired["content"]
            and bool(record.get("proxied", False)) == desired["proxied"]
            and int(record.get("ttl") or 0) == desired["ttl"]
        )

    async def create_dns_record(
        self,
        hostname: str,
        target: str,
        *,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict[str, Any]:
        payload = self._dns_payload(
            hostname,
            target,
            record_type=record_type,
            proxied=proxied,
            ttl=ttl,
        )
        return await self._request(
            "POST",
            await self._zone_path("/dns_records"),
            payload=payload,
        )

    async def update_dns_record(
        self,
        record_id: str,
        hostname: str,
        target: str,
        *,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict[str, Any]:
        payload = self._dns_payload(
            hostname,
            target,
            record_type=record_type,
            proxied=proxied,
            ttl=ttl,
        )
        return await self._request(
            "PUT",
            await self._zone_path(f"/dns_records/{record_id}"),
            payload=payload,
        )

    async def _verified_dns_state(
        self,
        desired: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        lookup = await self.list_dns_records(desired["name"], desired["type"])
        records = lookup.get("result")
        if isinstance(records, list):
            for item in records:
                if isinstance(item, dict) and self._dns_record_matches(item, desired):
                    return item, lookup
        return None, lookup

    async def ensure_dns_record(
        self,
        hostname: str,
        target: str,
        *,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict[str, Any]:
        desired = self._dns_payload(
            hostname,
            target,
            record_type=record_type,
            proxied=proxied,
            ttl=ttl,
        )
        if self.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "existing": False,
                "record_exists": True,
                "reconciled": True,
                "result": desired,
            }

        existing = await self.list_dns_records(desired["name"], desired["type"])
        raw_records = existing.get("result")
        records = [record for record in raw_records if isinstance(record, dict)] if isinstance(raw_records, list) else []

        exact = next((record for record in records if self._dns_record_matches(record, desired)), None)
        if exact is not None:
            return {
                "success": True,
                "existing": True,
                "record_exists": True,
                "reconciled": False,
                "result": exact,
                "lookup": existing,
                "duplicate_count": max(len(records) - 1, 0),
            }

        # Prefere reconciliar um registro com o mesmo conteúdo; caso contrário, o
        # registro do mesmo nome/tipo é sobrescrito. Nunca aceita estado incorreto.
        same_content = next(
            (
                record
                for record in records
                if self._clean_content(str(record.get("content") or ""), desired["type"])
                == desired["content"]
            ),
            None,
        )
        candidate = same_content or (records[0] if records else None)
        operation = "create"
        try:
            if candidate is not None and candidate.get("id"):
                operation = "update"
                response = await self.update_dns_record(
                    str(candidate["id"]),
                    desired["name"],
                    desired["content"],
                    record_type=desired["type"],
                    proxied=desired["proxied"],
                    ttl=desired["ttl"],
                )
            else:
                response = await self.create_dns_record(
                    desired["name"],
                    desired["content"],
                    record_type=desired["type"],
                    proxied=desired["proxied"],
                    ttl=desired["ttl"],
                )
        except APIError as exc:
            verified, lookup = await self._verified_dns_state(desired)
            if verified is not None:
                return {
                    "success": True,
                    "existing": True,
                    "record_exists": True,
                    "reconciled": True,
                    "recovered_after_api_error": True,
                    "result": verified,
                    "lookup": lookup,
                }
            raise APIError(
                "CLOUDFLARE_DNS_RECONCILIATION_ERROR",
                "A Cloudflare não convergiu o DNS para o estado solicitado.",
                424,
                {
                    "desired": desired,
                    "existing": lookup.get("result"),
                    "operation": operation,
                    "cloudflare_error": {
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    },
                },
            ) from exc

        verified, lookup = await self._verified_dns_state(desired)
        if verified is None:
            raise APIError(
                "CLOUDFLARE_DNS_RECONCILIATION_ERROR",
                "A Cloudflare respondeu com sucesso, mas o DNS ainda não está no estado solicitado.",
                424,
                {
                    "desired": desired,
                    "observed": lookup.get("result"),
                    "operation": operation,
                    "response": response,
                },
            )
        return {
            "success": True,
            "existing": candidate is not None,
            "record_exists": True,
            "reconciled": True,
            "operation": operation,
            "result": verified,
            "cloudflare": response,
            "lookup": lookup,
            "duplicate_count": max(len(records) - 1, 0),
        }

    async def delete_dns_record(self, record_id: str) -> dict[str, Any]:
        return await self._request(
            "DELETE",
            await self._zone_path(f"/dns_records/{record_id}"),
        )

    async def list_custom_hostnames(self, hostname: str) -> dict[str, Any]:
        clean = self._clean_hostname(hostname)
        if self.dry_run:
            return self._dry_result("GET /custom_hostnames", {"hostname": clean, "records": []})
        path = await self._zone_path("/custom_hostnames")
        # A API representa o filtro aninhado como hostname.exact na query string.
        return await self._request(
            "GET",
            f"{path}?{urlencode({'hostname.exact': clean, 'per_page': '50'})}",
        )

    async def create_custom_hostname(self, hostname: str) -> dict[str, Any]:
        clean = self._clean_hostname(hostname)
        payload: dict[str, Any] = {
            "hostname": clean,
            "ssl": {
                "method": "http",
                "type": "dv",
                "certificate_authority": self.custom_hostname_ca,
                "settings": {"http2": "on", "min_tls_version": "1.2", "tls_1_3": "on"},
            },
        }
        if self.custom_hostname_origin:
            payload["custom_origin_server"] = self.custom_hostname_origin
        return await self._request(
            "POST",
            await self._zone_path("/custom_hostnames"),
            payload=payload,
        )

    async def ensure_custom_hostname(self, hostname: str) -> dict[str, Any]:
        clean = self._clean_hostname(hostname)
        if self.dry_run:
            return self._dry_result(
                "ENSURE /custom_hostnames",
                {
                    "hostname": clean,
                    "status": "active",
                    "ssl": {"status": "active", "certificate_authority": self.custom_hostname_ca},
                },
            )

        lookup = await self.list_custom_hostnames(clean)
        raw = lookup.get("result")
        records = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        usable = next(
            (
                item
                for item in records
                if self._clean_hostname(str(item.get("hostname") or "")) == clean
                and str(item.get("status") or "") not in {"deleted", "pending_deletion"}
            ),
            None,
        )
        if usable is not None:
            return {
                "success": True,
                "existing": True,
                "result": usable,
                "lookup": lookup,
            }

        try:
            created = await self.create_custom_hostname(clean)
        except APIError as exc:
            after = await self.list_custom_hostnames(clean)
            after_records = after.get("result")
            recovered = next(
                (
                    item
                    for item in after_records
                    if isinstance(item, dict)
                    and self._clean_hostname(str(item.get("hostname") or "")) == clean
                    and str(item.get("status") or "") not in {"deleted", "pending_deletion"}
                ),
                None,
            ) if isinstance(after_records, list) else None
            if recovered is not None:
                return {
                    "success": True,
                    "existing": True,
                    "recovered_after_create_error": True,
                    "result": recovered,
                    "lookup": after,
                }
            raise exc
        return {
            "success": True,
            "existing": False,
            "result": created.get("result"),
            "cloudflare": created,
        }

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
        return await self.ensure_custom_hostname(hostname)

    async def get_validation_status(self, hostname_id: str) -> dict[str, Any]:
        return await self.get_custom_hostname_status(hostname_id)

    async def purge_cache(self, hostname: str) -> dict[str, Any]:
        payload = {"hosts": [self._clean_hostname(hostname)]}
        return await self._request(
            "POST",
            await self._zone_path("/purge_cache"),
            payload=payload,
        )
