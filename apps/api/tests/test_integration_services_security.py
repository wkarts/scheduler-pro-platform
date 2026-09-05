"""Executable regressions for service-token isolation, replay and signed HTTPS delivery."""

import asyncio
import base64
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import hmac
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI
import httpx
import pytest

from app.core.errors import APIError
from app.core.secrets import seal_secret
from app.core.security import AuthPrincipal
from app.core.tenant_context import TenantContext
from app.integration_services import catalog, middleware, webhooks
from app.integration_services.auth import IntegrationIdentity, TOKEN_PATTERN, authenticate_token
from app.integration_services.ledger import (
    Reservation,
    authorization_snapshot,
    replay_authorized,
    request_fingerprint,
)


def identity() -> IntegrationIdentity:
    context = TenantContext(
        tenant_id=str(uuid4()),
        slug="test",
        database="test",
        database_user="test",
        database_password_ref="secret://env/TEST",
        hostname="test.example.com",
        storage_bucket="test",
    )
    return IntegrationIdentity(
        AuthPrincipal(
            user_id=str(uuid4()),
            email="user@example.com",
            user_type="tenant",
            tenant_id=context.tenant_id,
            session_id="",
            permissions=frozenset({"customers.read", "customers.manage"}),
            roles=frozenset({"tenant-admin"}),
            tenant_ids=frozenset({context.tenant_id}),
        ),
        context,
        str(uuid4()),
        frozenset({"customers.read", "customers.write"}),
        frozenset({"customers"}),
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/webhook",
        "https://example.com:8080/",
        "https://user:pass@example.com/",
        "https://127.0.0.1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://10.0.0.1/",
        "https://localhost/",
        "https://db.internal/",
        "https://[::1]/",
        "https://[::ffff:127.0.0.1]/",
        "https://example.com/#fragment",
        "https://example.com/\r\nheader",
        "https://example.com\\@127.0.0.1",
        "https://100.100.100.200/",
        "https://[fe80::1]/",
        "https://224.0.0.1/",
    ],
)
def test_rejects_unsafe_webhook_urls(url: str) -> None:
    with pytest.raises(webhooks.UnsafeWebhookTarget):
        webhooks.validate_url(url)


@pytest.mark.parametrize("url", ["https://example.com/events", "https://8.8.8.8:443/events"])
def test_accepts_public_https_syntax_without_claiming_reachability(url: str) -> None:
    assert webhooks.validate_url(url) == url


@pytest.mark.asyncio
async def test_dns_rebinding_mixed_public_private_answers_fail_closed(monkeypatch: Any) -> None:
    async def resolve(*args: Any, **kwargs: Any) -> list[Any]:
        return [(2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", ("10.0.0.1", 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    with pytest.raises(webhooks.UnsafeWebhookTarget):
        await webhooks.resolve_public_addresses("https://example.com/events")


@pytest.mark.asyncio
async def test_delivery_pins_dns_keeps_tls_name_and_does_not_follow_redirects(
    monkeypatch: Any,
) -> None:
    calls: list[httpx.Request] = []
    secret = "whsec_test-secret"

    async def addresses(_: str) -> tuple[str, list[str]]:
        return "example.com", ["8.8.8.8"]

    def receive(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.host == "8.8.8.8"
        assert request.headers["host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        expected = webhooks.signature(
            secret,
            request.headers["x-scheduler-timestamp"],
            request.headers["x-scheduler-delivery-id"],
            request.content,
        )
        assert hmac.compare_digest(expected, request.headers["x-scheduler-signature"])
        assert request.headers["authorization"] == "Bearer receiver-token"
        return httpx.Response(302, headers={"location": "http://127.0.0.1/"})

    original_client = httpx.AsyncClient

    def client(**kwargs: Any) -> httpx.AsyncClient:
        assert kwargs["verify"] is True and kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return original_client(transport=httpx.MockTransport(receive), **kwargs)

    monkeypatch.setattr(webhooks, "resolve_public_addresses", addresses)
    monkeypatch.setattr(webhooks.httpx, "AsyncClient", client)
    status, _ = await webhooks.send_delivery(
        {
            "id": str(uuid4()),
            "event_id": str(uuid4()),
            "event_type": "customer.created",
            "event_created_at": datetime.now(UTC),
            "payload": {"resource_id": str(uuid4())},
            "url": "https://example.com/events",
            "secret_ref": seal_secret(secret),
            "authorization_ref": seal_secret("receiver-token"),
            "attempts": 1,
        },
        None,
    )
    assert status == 302 and len(calls) == 1


def test_signing_binds_exact_body_timestamp_and_delivery() -> None:
    expected = "v1=" + hmac.new(b"secret", b'123.id.{"ok":true}', sha256).hexdigest()
    assert webhooks.signature("secret", "123", "id", b'{"ok":true}') == expected
    assert webhooks.signature("secret", "124", "id", b'{"ok":true}') != expected
    assert webhooks.signature("secret", "123", "other", b'{"ok":true}') != expected
    assert webhooks.signature("secret", "123", "id", b'{"ok":false}') != expected


def test_replay_fingerprint_binds_body_query_path_and_content_type() -> None:
    args = ["POST", "/api/v1/customers", "", "application/json", b"{}"]
    original = request_fingerprint(*args)
    for index, value in enumerate(["PATCH", "/api/v1/services", "x=1", "text/plain", b'{"x":1}']):
        changed = args.copy()
        changed[index] = value
        assert request_fingerprint(*changed) != original


def test_replay_permissions_allow_additions_but_never_revocations() -> None:
    before = identity()
    saved = authorization_snapshot(before)
    expanded = replace(
        before,
        principal=replace(
            before.principal, tenant_ids=before.principal.tenant_ids | {str(uuid4())}
        ),
    )
    assert replay_authorized(saved, expanded)
    revoked = replace(before, principal=replace(before.principal, permissions=frozenset()))
    assert not replay_authorized(saved, revoked)
    assert not replay_authorized(saved, replace(before, capabilities=frozenset()))
    assert not replay_authorized(
        saved, replace(before, principal=replace(before.principal, roles=frozenset()))
    )


@pytest.mark.asyncio
async def test_platform_credential_cannot_authenticate_a_tenant() -> None:
    raw = "sp_p_" + uuid4().hex + "." + "a" * 43
    assert TOKEN_PATTERN.fullmatch(raw)
    with pytest.raises(APIError) as error:
        await authenticate_token(raw, identity().context, "customers.read")
    assert error.value.status_code == 401


def test_explicit_machine_surface_excludes_auth_tokens_public_and_superadmin() -> None:
    app = FastAPI()

    async def get_current_tenant_user() -> None:
        pass

    async def require_super_admin() -> None:
        pass

    @app.get("/api/v1/customers", dependencies=[Depends(get_current_tenant_user)])
    async def customers() -> dict:
        return {}

    @app.get("/api/v1/customers/public")
    async def public() -> dict:
        return {}

    @app.delete(
        "/api/v1/customers/root",
        dependencies=[Depends(get_current_tenant_user), Depends(require_super_admin)],
    )
    async def root() -> dict:
        return {}

    assert [item["path"] for item in catalog.operation_catalog(app, False)] == ["/api/v1/customers"]
    assert catalog.scope_for("/api/v1/auth/login", "POST", False) is None
    assert catalog.scope_for("/api/v1/integrations/services/tokens", "POST", False) is None
    assert catalog.scope_for("/api/v1/customers", "GET", True) is None
    assert catalog.scope_for("/api/v1/platform/tenants", "GET", False) is None


@pytest.fixture
def memory_boundary(monkeypatch: Any) -> SimpleNamespace:
    current = identity()
    state = SimpleNamespace(calls=0, reservations={}, fail_persist=False, crash=False)

    async def scope(*args: Any) -> TenantContext | None:
        return current.context

    async def authenticate(*args: Any) -> IntegrationIdentity:
        return current

    async def reserve(_, key: str, fingerprint: str, *args: Any) -> Reservation:
        if len(key) < 8:
            raise APIError("IDEMPOTENCY_KEY_REQUIRED", "key required", 400)
        previous = state.reservations.get(key)
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise APIError("IDEMPOTENCY_CONFLICT", "conflict", 409)
            if previous["response"]:
                return Reservation(key, previous["response"])
            raise APIError("IDEMPOTENCY_OUTCOME_UNKNOWN", "unknown", 409)
        state.reservations[key] = {"fingerprint": fingerprint, "response": None, "unknown": False}
        return Reservation(key)

    async def complete(_, request_id: str, status: int, headers: Any, body: bytes | None) -> None:
        if state.fail_persist:
            raise OSError("database unavailable")
        state.reservations[request_id]["response"] = {
            "status": status,
            "headers": [],
            "body": base64.b64encode(body or b"").decode(),
        }

    async def unknown(_, request_id: str) -> None:
        state.reservations[request_id]["unknown"] = True

    async def business(scope: Any, receive: Any, send: Any) -> None:
        state.calls += 1
        if state.crash:
            raise RuntimeError("crash after possible side effect")
        if scope["method"] != "GET":
            await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 201,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"data":{"created":true}}'})

    monkeypatch.setattr(middleware, "resolve_scope", scope)
    monkeypatch.setattr(middleware, "authenticate_token", authenticate)
    monkeypatch.setattr(middleware, "match_operation", lambda *args: "customers.write")
    monkeypatch.setattr(middleware, "reserve", reserve)
    monkeypatch.setattr(middleware, "complete", complete)
    monkeypatch.setattr(middleware, "mark_unknown", unknown)
    state.app = middleware.ServiceAPIMiddleware(business, application=FastAPI())
    return state


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.asyncio
async def test_repeated_mutation_replays_without_dispatching_twice(
    memory_boundary: Any, method: str
) -> None:
    state = memory_boundary
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=state.app), base_url="https://example.com"
    ) as client:
        headers = {"authorization": "Bearer sp_t_test", "idempotency-key": "same-request-123"}
        first = await client.request(method, "/api/v1/customers", headers=headers, content=b"{}")
        second = await client.request(method, "/api/v1/customers", headers=headers, content=b"{}")
        different = await client.request(
            method, "/api/v1/customers", headers=headers, content=b'{"x":1}'
        )
    assert first.status_code == second.status_code == 201
    assert first.content == second.content and second.headers["idempotency-replayed"] == "true"
    assert different.status_code == 409 and state.calls == 1


@pytest.mark.asyncio
async def test_ambiguous_business_failure_never_redispatches(memory_boundary: Any) -> None:
    state = memory_boundary
    state.crash = True
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=state.app), base_url="https://example.com"
    ) as client:
        headers = {"authorization": "Bearer sp_t_test", "idempotency-key": "uncertain-request"}
        first = await client.post("/api/v1/customers", headers=headers, json={})
        second = await client.post("/api/v1/customers", headers=headers, json={})
    assert first.status_code == 500 and second.status_code == 409
    assert state.calls == 1 and state.reservations["uncertain-request"]["unknown"]


@pytest.mark.asyncio
async def test_response_persistence_failure_keeps_reservation(memory_boundary: Any) -> None:
    state = memory_boundary
    state.fail_persist = True
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=state.app), base_url="https://example.com"
    ) as client:
        headers = {"authorization": "Bearer sp_t_test", "idempotency-key": "persistence-failure"}
        assert (await client.post("/api/v1/customers", headers=headers, json={})).status_code == 201
        assert (await client.post("/api/v1/customers", headers=headers, json={})).status_code == 409
    assert state.calls == 1


@pytest.mark.asyncio
async def test_missing_key_and_oversized_request_never_call_business(
    memory_boundary: Any, monkeypatch: Any
) -> None:
    state = memory_boundary
    monkeypatch.setattr(middleware.config, "max_request_bytes", 1024)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=state.app), base_url="https://example.com"
    ) as client:
        headers = {"authorization": "Bearer sp_t_test"}
        assert (await client.post("/api/v1/customers", headers=headers, json={})).status_code == 400
        headers["idempotency-key"] = "oversized-request"
        assert (
            await client.post("/api/v1/customers", headers=headers, content=b"x" * 1025)
        ).status_code == 413
    assert state.calls == 0


def test_images_build_only_amd64_but_mobile_targets_remain() -> None:
    root = Path(__file__).resolve().parents[3]
    for name in ("images.yml", "homolog-images.yml", "base-image.yml"):
        source = (root / ".github/workflows" / name).read_text()
        assert "platforms: linux/amd64" in source
        assert "linux/arm64" not in source and "setup-qemu" not in source
    assert "aarch64" in (root / ".github/workflows/mobile-artifacts.yml").read_text()


@pytest.mark.parametrize("address", ["64:ff9b::a00:1", "64:ff9b:1::1", "2002:7f00:1::1", "2001::1"])
def test_ipv6_transition_destinations_are_not_egress_bypasses(address: str) -> None:
    with pytest.raises(webhooks.UnsafeWebhookTarget):
        webhooks.ensure_public_ip(address)


def test_replay_cannot_restore_global_administration_after_demotion() -> None:
    before = replace(identity(), context=None, control_plane_global=True)
    assert not replay_authorized(
        authorization_snapshot(before), replace(before, control_plane_global=False)
    )


def test_global_webhook_management_is_not_granted_to_restricted_platform_admin() -> None:
    from starlette.requests import Request
    from app.integration_services.routes import webhook_identity

    current = replace(
        identity(),
        context=None,
        principal=replace(
            identity().principal,
            user_type="platform",
            tenant_id=None,
            permissions=frozenset({"integrations.manage"}),
        ),
    )
    request = Request({"type": "http", "state": {"integration_identity": current}})
    with pytest.raises(APIError) as error:
        webhook_identity(request)
    assert error.value.code == "GLOBAL_WEBHOOK_ACCESS_REQUIRED"
    request.state.integration_identity = replace(current, control_plane_global=True)
    assert webhook_identity(request).control_plane_global


@pytest.mark.asyncio
async def test_admission_limit_protects_authentication_itself(
    memory_boundary: Any, monkeypatch: Any
) -> None:
    state = memory_boundary
    state.app.inflight = middleware.config.max_inflight_requests

    async def forbidden(*args: Any) -> None:
        raise AssertionError("Database authentication must not start when the boundary is full")

    monkeypatch.setattr(middleware, "authenticate_token", forbidden)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=state.app), base_url="https://example.com"
    ) as client:
        response = await client.get(
            "/api/v1/customers", headers={"authorization": "Bearer sp_t_test"}
        )
    assert response.status_code == 503 and state.calls == 0
    assert state.app.inflight == middleware.config.max_inflight_requests


@pytest.mark.asyncio
async def test_service_reads_disable_caching_and_release_admission(memory_boundary: Any) -> None:
    state = memory_boundary
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=state.app), base_url="https://example.com"
    ) as client:
        response = await client.get(
            "/api/v1/customers", headers={"authorization": "Bearer sp_t_test"}
        )
    assert response.headers["cache-control"] == "no-store"
    assert state.app.inflight == 0
