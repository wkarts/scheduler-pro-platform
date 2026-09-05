"""HTTPS-only signed deliveries with DNS pinning and no database connection during IO."""

import asyncio
from datetime import UTC, datetime
from hashlib import sha256
import hmac
import ipaddress
import json
import random
import socket
import time
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import text

from app.core.errors import APIError
from app.core.secrets import secret_resolver
from app.core.tenant_context import TenantContext
from app.integration_services.auth import integration_session
from app.integration_services.config import integration_settings as config


class UnsafeWebhookTarget(ValueError):
    pass


def validate_url(url: str) -> str:
    try:
        if len(url) > 2048 or any(c.isspace() or ord(c) < 32 for c in url) or "\\" in url:
            raise ValueError("invalid characters")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.port not in {None, 443}
        ):
            raise ValueError("HTTPS port 443 required")
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        if (
            "%" in host
            or host == "localhost"
            or host.endswith((".local", ".internal", ".localhost"))
        ):
            raise ValueError("local hostname")
        try:
            ensure_public_ip(host)
        except ValueError as exc:
            # A non-IP DNS name is resolved and checked before each delivery.
            try:
                ipaddress.ip_address(host)
            except ValueError:
                if "." not in host or not all(part and len(part) <= 63 for part in host.split(".")):
                    raise UnsafeWebhookTarget("Hostname público inválido.") from exc
            else:
                raise
        return url
    except (ValueError, UnicodeError) as exc:
        raise UnsafeWebhookTarget(
            "Destino deve usar HTTPS público na porta 443, sem credenciais."
        ) from exc


def ensure_public_ip(value: str) -> str:
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if isinstance(address, ipaddress.IPv6Address) and any(
        address in ipaddress.ip_network(prefix)
        for prefix in ("64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "2001::/32")
    ):
        raise UnsafeWebhookTarget("Endereço de transição IPv6 não permitido.")
    if (
        not address.is_global
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        or address.is_loopback
        or address.is_link_local
    ):
        raise UnsafeWebhookTarget("Endereço privado, reservado ou de metadados bloqueado.")
    return str(address)


async def resolve_public_addresses(url: str) -> tuple[str, list[str]]:
    validate_url(url)
    hostname = str(urlsplit(url).hostname).encode("idna").decode("ascii").lower().rstrip(".")
    try:
        addresses = [ensure_public_ip(hostname)]
    except ValueError:
        records = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(hostname, 443, type=socket.SOCK_STREAM),
            timeout=3,
        )
        addresses = list(dict.fromkeys(ensure_public_ip(str(item[4][0])) for item in records))
    if not addresses:
        raise UnsafeWebhookTarget("Destino sem endereço público.")
    return hostname, addresses


def signature(secret: str, timestamp: str, delivery_id: str, body: bytes) -> str:
    signed = timestamp.encode() + b"." + delivery_id.encode() + b"." + body
    return "v1=" + hmac.new(secret.encode(), signed, sha256).hexdigest()


async def send_delivery(
    delivery: dict[str, Any], context: TenantContext | None
) -> tuple[int, int | None]:
    hostname, addresses = await resolve_public_addresses(delivery["url"])
    envelope = {
        "specversion": "1.0",
        "id": str(delivery["event_id"]),
        "source": f"urn:scheduler-pro:tenant:{context.tenant_id}"
        if context
        else "urn:scheduler-pro:platform",
        "type": delivery["event_type"],
        "time": delivery["event_created_at"].isoformat(),
        "scope": "platform" if context is None else "tenant",
        "tenant_id": context.tenant_id if context else None,
        "data": delivery["payload"],
    }
    body = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    timestamp = str(int(time.time()))
    headers = {
        "Host": f"[{hostname}]" if ":" in hostname else hostname,
        "Content-Type": "application/json",
        "User-Agent": "Scheduler-Pro-Webhooks/1.0",
        "X-Scheduler-Event": delivery["event_type"],
        "X-Scheduler-Event-Id": str(delivery["event_id"]),
        "X-Scheduler-Delivery-Id": str(delivery["id"]),
        "X-Scheduler-Timestamp": timestamp,
        "X-Scheduler-Signature": signature(
            secret_resolver.resolve(delivery["secret_ref"]), timestamp, str(delivery["id"]), body
        ),
    }
    if delivery.get("authorization_ref"):
        headers["Authorization"] = "Bearer " + secret_resolver.resolve(
            delivery["authorization_ref"]
        )
    # URL uses the validated IP, while Host/SNI still validate the original TLS name.
    # There is no second DNS resolution and no environment proxy/redirect escape.
    target = httpx.URL(delivery["url"]).copy_with(
        host=addresses[(int(delivery["attempts"]) - 1) % len(addresses)]
    )
    async with asyncio.timeout(config.webhook_timeout_seconds):
        async with httpx.AsyncClient(
            timeout=config.webhook_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            verify=True,
        ) as client:
            async with client.stream(
                "POST", target, content=body, headers=headers, extensions={"sni_hostname": hostname}
            ) as response:
                retry_after = response.headers.get("retry-after", "")
                retry = min(int(retry_after), 3600) if retry_after.isdigit() else None
                return response.status_code, retry


def retry_delay(attempt: int, server_delay: int | None = None) -> int:
    base = min(3600, 15 * (2 ** min(max(attempt - 1, 0), 8)))
    return int(
        min(3600, max(server_delay or 0, base + random.SystemRandom().randint(0, base // 4)))
    )


async def claim_delivery(context: TenantContext | None) -> dict[str, Any] | None:
    async with integration_session(context) as session:
        # Removing an owner's authorization also suspends further outbound access.
        owner_predicate = (
            "select 1 from platform_users u where u.id=e.created_by and u.is_active and u.is_super_admin"
            if context is None
            else "select 1 from users u join user_roles ur on ur.user_id=u.id "
            "join role_permissions rp on rp.role_id=ur.role_id "
            "join roles active_role on active_role.id=ur.role_id and active_role.is_active "
            "join permissions p on p.id=rp.permission_id "
            "where u.id=e.created_by and u.is_active and p.key='tenant.manage' "
            "and (not u.verification_required or u.email_verified_at is not null)"
        )
        await session.execute(
            text(
                "update service_webhook_endpoints e set active=false,updated_at=now() "
                f"where e.active and not exists({owner_predicate})"
            )
        )
        await session.execute(
            text(
                "update service_webhook_deliveries set state='failed',last_error='attempts_exhausted' "
                "where state='sending' and lease_until<now() and cycle_attempts>=:maximum"
            ),
            {"maximum": config.webhook_max_attempts},
        )
        await session.execute(
            text(
                "update service_webhook_deliveries d set state='cancelled',lease_id=null,lease_until=null "
                "where state in ('pending','sending') "
                "and exists(select 1 from service_webhook_endpoints e where e.id=d.endpoint_id "
                "and e.deleted_at is not null)"
            )
        )
        lease_id = str(uuid4())
        delivery_id = (
            await session.execute(
                text(
                    "with candidate as (select d.id from service_webhook_deliveries d "
                    "join service_webhook_endpoints e on e.id=d.endpoint_id and e.active and e.deleted_at is null "
                    "where d.cycle_attempts<:maximum and d.available_at<=now() "
                    "and (d.state='pending' or (d.state='sending' and d.lease_until<now())) "
                    "order by d.available_at,d.id for update of d skip locked limit 1) "
                    "update service_webhook_deliveries d set state='sending',attempts=d.attempts+1,"
                    "cycle_attempts=d.cycle_attempts+1,lease_id=cast(:lease as uuid),"
                    "lease_until=now()+interval '60 seconds' from candidate c where d.id=c.id "
                    "returning d.id::text"
                ),
                {"maximum": config.webhook_max_attempts, "lease": lease_id},
            )
        ).scalar_one_or_none()
        if delivery_id is None:
            await session.commit()
            return None
        row = (
            (
                await session.execute(
                    text(
                        "select d.*, e.url,e.secret_ref,e.authorization_ref, v.event_type,v.payload,"
                        "v.created_at as event_created_at from service_webhook_deliveries d "
                        "join service_webhook_endpoints e on e.id=d.endpoint_id "
                        "join service_webhook_events v on v.id=d.event_id where d.id=cast(:id as uuid)"
                    ),
                    {"id": delivery_id},
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            text(
                "insert into service_webhook_attempts(id,delivery_id,attempt) "
                "values(cast(:lease as uuid),cast(:id as uuid),:attempt)"
            ),
            {"lease": lease_id, "id": delivery_id, "attempt": row["attempts"]},
        )
        await session.commit()
        return dict(row)


async def finish_delivery(
    context: TenantContext | None,
    delivery: dict[str, Any],
    *,
    status: int | None,
    error: str | None,
    retry_after: int | None = None,
) -> None:
    successful = status is not None and 200 <= status < 300
    retryable = error != "unsafe_target" and (
        status is None or status in {408, 425, 429} or status >= 500
    )
    state = (
        "delivered"
        if successful
        else "pending"
        if retryable and delivery["cycle_attempts"] < config.webhook_max_attempts
        else "failed"
    )
    async with integration_session(context) as session:
        await session.execute(
            text(
                "update service_webhook_deliveries set state=cast(:state as varchar(16)),http_status=:status,last_error=:error,"
                "available_at=now()+make_interval(secs=>:delay),lease_id=null,lease_until=null,"
                "delivered_at=case when cast(:state as varchar(16))='delivered' then now() else delivered_at end "
                "where id=cast(:id as uuid) and lease_id=cast(:lease as uuid) and state='sending'"
            ),
            {
                "id": str(delivery["id"]),
                "lease": str(delivery["lease_id"]),
                "state": state,
                "status": status,
                "error": error,
                "delay": retry_delay(delivery["cycle_attempts"], retry_after),
            },
        )
        await session.execute(
            text(
                "update service_webhook_attempts set finished_at=now(),http_status=:status,error=:error "
                "where id=cast(:lease as uuid)"
            ),
            {"lease": str(delivery["lease_id"]), "status": status, "error": error},
        )
        await session.commit()


async def drain(context: TenantContext | None) -> dict[str, int]:
    if not config.webhooks_enabled:
        return {"processed": 0}
    count = 0
    for _ in range(config.webhook_batch_size):
        delivery = await claim_delivery(context)
        if delivery is None:
            break
        status, retry = None, None
        error = None
        try:
            status, retry = await send_delivery(delivery, context)
            if not 200 <= status < 300:
                error = f"http_{status}"
        except UnsafeWebhookTarget:
            error = "unsafe_target"
        except Exception as exc:
            # No URL, credential, response body or exception text enters delivery logs.
            error = type(exc).__name__[:120]
        await finish_delivery(context, delivery, status=status, error=error, retry_after=retry)
        count += 1
    return {"processed": count}


async def cleanup(context: TenantContext | None) -> None:
    async with integration_session(context) as session:
        # Erase incoming contents on retention, never their idempotency tombstones.
        await session.execute(
            text(
                "update service_webhook_inbox set payload_sealed=null where payload_sealed is not null and payload_expires_at<=now()"
            )
        )
        await session.execute(
            text(
                "update service_api_requests set response_sealed=null,state='response_expired' "
                "where state='completed' and created_at<now()-make_interval(hours=>:hours)"
            ),
            {"hours": config.replay_hours},
        )
        # Unknown/processing outcomes are intentionally never released automatically.
        await session.execute(
            text(
                "update service_api_requests set resolution_note=null where resolution_note is not null "
                "and state in ('response_expired','resolved') "
                "and created_at<now()-make_interval(days=>:days)"
            ),
            {"days": config.retention_days},
        )
        await session.execute(
            text(
                "delete from service_webhook_events e where e.created_at<now()-make_interval(days=>:days) "
                "and not exists(select 1 from service_webhook_deliveries d where d.event_id=e.id "
                "and d.state in ('pending','sending'))"
            ),
            {"days": config.retention_days},
        )
        await session.commit()


async def enqueue_test(context: TenantContext | None, endpoint_id: str) -> str:
    async with integration_session(context) as session:
        active = (
            await session.execute(
                text(
                    "select id from service_webhook_endpoints where id=cast(:id as uuid) "
                    "and active and deleted_at is null for update"
                ),
                {"id": endpoint_id},
            )
        ).scalar_one_or_none()
        if active is None:
            raise APIError("WEBHOOK_NOT_ACTIVE", "Destino inexistente ou pausado.", 409)
        event_id, delivery_id = str(uuid4()), str(uuid4())
        await session.execute(
            text(
                "insert into service_webhook_events(id,event_type,payload) "
                "values(cast(:id as uuid),'webhook.test',cast(:body as jsonb))"
            ),
            {
                "id": event_id,
                "body": json.dumps(
                    {
                        "message": "Teste de integração Scheduler Pro",
                        "requested_at": datetime.now(UTC).isoformat(),
                    }
                ),
            },
        )
        await session.execute(
            text(
                "insert into service_webhook_deliveries(id,endpoint_id,event_id) "
                "values(cast(:id as uuid),cast(:endpoint as uuid),cast(:event as uuid))"
            ),
            {"id": delivery_id, "endpoint": endpoint_id, "event": event_id},
        )
        await session.commit()
        return delivery_id
