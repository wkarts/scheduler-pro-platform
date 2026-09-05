"""Real PostgreSQL + HTTP regressions; outbound network is mocked, never a public receiver."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from hashlib import sha256
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.errors import APIError
from app.integration_services.auth import IntegrationIdentity, current_owner, integration_session
from app.integration_services import ledger, routes, webhooks
from app.services.tenant_resolver import TenantResolver
from app.workers.celery_app import celery_app
from test_foundation_integration import (
    tenant_login,
    platform_login_with_second_factor,
    _prepare_second_tenant,
)

pytestmark = pytest.mark.integration
BASE = "/api/v1/integrations/services"
PLATFORM = "/api/v1/platform/integrations/services"


@asynccontextmanager
async def db():
    connection = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.dev_tenant_database_user,
        password=settings.dev_tenant_database_password,
        database=settings.dev_tenant_database,
    )
    try:
        yield connection
    finally:
        await connection.close()


async def tenant_identity():
    async with integration_session(None) as session:
        context = await TenantResolver(session).resolve("localhost")
    async with integration_session(context) as session:
        owner_id = await session.scalar(
            text("select id::text from users where email=:email"),
            {"email": settings.dev_tenant_admin_email},
        )
        principal = await current_owner(session, str(owner_id), context)
    return IntegrationIdentity(principal, context, str(uuid4()))


def headers(token: str, key: str | None = None) -> dict[str, str]:
    result = {"authorization": f"Bearer {token}"}
    if key is not None:
        result["idempotency-key"] = key
    return result


async def issue(
    client: httpx.AsyncClient, access: str, scopes: list[str], *, platform=False, rate=120
):
    response = await client.post(
        (PLATFORM if platform else BASE) + "/tokens",
        headers=headers(access, str(uuid4())),
        json={"name": "Integration regression", "scopes": scopes, "rate_limit": rate},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_machine_tokens_isolation_hash_revocation_rotation_and_live_permissions(
    client: httpx.AsyncClient,
):
    login = await tenant_login(client)
    access = login["access_token"]
    key = str(uuid4())
    payload = {
        "name": "Individual ERP",
        "scopes": ["customers.read", "customers.write", "integrations.services.read"],
    }
    one = await client.post(BASE + "/tokens", headers=headers(access, key), json=payload)
    two = await client.post(BASE + "/tokens", headers=headers(access, key), json=payload)
    assert one.status_code == two.status_code == 201, one.text
    assert one.content == two.content and two.headers["idempotency-replayed"] == "true"
    token = one.json()["data"]["token"]
    token_id = one.json()["data"]["id"]
    async with db() as conn:
        stored = await conn.fetchval(
            "select token_hash from service_api_tokens where id=$1::uuid", token_id
        )
        assert stored == sha256(token.encode()).hexdigest()
    listing = await client.get(BASE + "/tokens", headers=headers(access))
    assert token not in listing.text and "token_hash" not in listing.text
    assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 200
    assert (await client.get("/api/v1/platform/tenants", headers=headers(token))).status_code == 401
    assert (
        await client.post(BASE + "/tokens", headers=headers(token, str(uuid4())), json=payload)
    ).status_code == 403
    before = await client.post(
        "/api/v1/customers", headers=headers(token), json={"name": "Do not create"}
    )
    assert before.status_code == 400
    customer_key = str(uuid4())
    name = "Idempotent " + uuid4().hex
    create = await client.post(
        "/api/v1/customers", headers=headers(token, customer_key), json={"name": name}
    )
    assert create.status_code == 200, create.text
    again = await client.post(
        "/api/v1/customers", headers=headers(token, customer_key), json={"name": name}
    )
    assert again.content == create.content and again.headers["idempotency-replayed"] == "true"
    conflict = await client.post(
        "/api/v1/customers", headers=headers(token, customer_key), json={"name": "Different"}
    )
    assert conflict.status_code == 409
    async with db() as conn:
        assert await conn.fetchval("select count(*) from customers where name=$1", name) == 1
    rotation = await client.post(
        BASE + f"/tokens/{token_id}/rotate", headers=headers(access, str(uuid4())), json={}
    )
    assert rotation.status_code == 200, rotation.text
    rotated = rotation.json()["data"]["token"]
    assert rotated != token
    assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 401
    replay = await client.post(
        "/api/v1/customers", headers=headers(rotated, customer_key), json={"name": name}
    )
    assert replay.content == create.content and replay.headers["idempotency-replayed"] == "true"
    # Removing a permission from the owner's role must revoke its effect immediately.
    async with db() as conn:
        removed = await conn.fetch(
            "delete from role_permissions rp using user_roles ur,permissions p "
            "where rp.role_id=ur.role_id and p.id=rp.permission_id and p.key=$1 "
            "and ur.user_id=$2::uuid returning rp.role_id,rp.permission_id",
            "customers.read",
            one.json()["data"]["owner_id"],
        )
        assert removed
        try:
            assert (
                await client.get("/api/v1/customers", headers=headers(rotated))
            ).status_code == 403
            prior = await client.post(
                "/api/v1/customers", headers=headers(rotated, customer_key), json={"name": name}
            )
            assert (
                prior.status_code == 403
                and prior.json()["error"]["code"] == "IDEMPOTENCY_REPLAY_FORBIDDEN"
            )
        finally:
            for item in removed:
                await conn.execute(
                    "insert into role_permissions(role_id,permission_id) values($1,$2) "
                    "on conflict do nothing",
                    item["role_id"],
                    item["permission_id"],
                )
    limited = await issue(client, access, ["customers.read"], rate=1)
    assert (
        await client.get("/api/v1/customers", headers=headers(limited["token"]))
    ).status_code == 200
    limited_response = await client.get("/api/v1/customers", headers=headers(limited["token"]))
    assert limited_response.status_code == 429 and "retry-after" in limited_response.headers
    readonly = await issue(client, access, ["customers.read"])
    denied = await client.post(
        "/api/v1/customers",
        headers=headers(readonly["token"], str(uuid4())),
        json={"name": "Denied"},
    )
    assert denied.status_code == 403
    other_host, _, _, _ = await _prepare_second_tenant()
    other = await client.get("/api/v1/customers", headers={**headers(rotated), "host": other_host})
    assert other.status_code == 401, other.text
    revoked = await client.delete(
        BASE + f"/tokens/{token_id}", headers=headers(access, str(uuid4()))
    )
    assert revoked.status_code == 200
    assert (await client.get("/api/v1/customers", headers=headers(rotated))).status_code == 401
    for item in (limited, readonly):
        assert (
            await client.delete(
                BASE + f"/tokens/{item['id']}", headers=headers(access, str(uuid4()))
            )
        ).status_code == 200


async def test_control_plane_tokens_use_distinct_scope_and_export_real_contract(
    client: httpx.AsyncClient,
):
    auth = await platform_login_with_second_factor(client)
    access = auth["access_token"]
    issued = await issue(client, access, ["tenants.read", "integrations.read"], platform=True)
    try:
        assert issued["token"].startswith("sp_p_")
        assert (
            await client.get("/api/v1/platform/tenants", headers=headers(issued["token"]))
        ).status_code == 200
        assert (
            await client.get("/api/v1/customers", headers=headers(issued["token"]))
        ).status_code == 401
        contract = await client.get(PLATFORM + "/openapi", headers=headers(issued["token"]))
        assert contract.status_code == 200, contract.text
        paths = contract.json()["paths"]
        assert "/api/v1/platform/tenants" in paths
        assert "/api/v1/auth/platform/login" not in paths
        assert PLATFORM + "/tokens" not in paths
        assert not any(path.startswith("/api/v1/customers") for path in paths)
    finally:
        await client.delete(
            PLATFORM + f"/tokens/{issued['id']}", headers=headers(access, str(uuid4()))
        )


async def test_real_idempotency_races_encrypted_replay_and_unknown_tombstones(
    client: httpx.AsyncClient,
):
    current = await tenant_identity()
    key = str(uuid4())
    fingerprint = ledger.request_fingerprint(
        "POST", "/api/v1/customers", "", "application/json", b"{}"
    )
    results = await asyncio.gather(
        *(ledger.reserve(current, key, fingerprint, "POST", "/api/v1/customers") for _ in range(6)),
        return_exceptions=True,
    )
    accepted = [result for result in results if isinstance(result, ledger.Reservation)]
    assert len(accepted) == 1
    assert all(isinstance(result, (ledger.Reservation, APIError)) for result in results), results
    request_id = accepted[0].id
    await ledger.complete(
        current, request_id, 201, [(b"content-type", b"application/json")], b'{"private":"value"}'
    )
    async with db() as conn:
        sealed = await conn.fetchval(
            "select response_sealed from service_api_requests where id=$1::uuid", request_id
        )
        assert sealed.startswith("secret://sealed/") and "private" not in sealed
    assert (await ledger.reserve(current, key, fingerprint, "POST", "/api/v1/customers")).replay[
        "status"
    ] == 201
    expanded = replace(
        current,
        principal=replace(
            current.principal, permissions=current.principal.permissions | {"new.permission"}
        ),
    )
    assert (
        await ledger.reserve(expanded, key, fingerprint, "POST", "/api/v1/customers")
    ).replay is not None
    uncertain_key = str(uuid4())
    uncertain = await ledger.reserve(
        current, uncertain_key, fingerprint, "POST", "/api/v1/customers"
    )
    await ledger.mark_unknown(current, uncertain.id)
    async with db() as conn:
        await conn.execute(
            "update service_api_requests set created_at=now()-interval '40 days' where id=$1::uuid",
            uncertain.id,
        )
    await webhooks.cleanup(current.context)
    with pytest.raises(APIError) as error:
        await ledger.reserve(current, uncertain_key, fingerprint, "POST", "/api/v1/customers")
    assert error.value.code == "IDEMPOTENCY_OUTCOME_UNKNOWN"


async def test_transactional_webhooks_rollbacks_pause_delivery_retry_and_lease_fencing(
    client: httpx.AsyncClient, monkeypatch: Any
):
    async def addresses(_: str):
        return "receiver.example.com", ["8.8.8.8"]

    monkeypatch.setattr(routes, "resolve_public_addresses", addresses)
    login = await tenant_login(client)
    access = login["access_token"]
    current = await tenant_identity()
    callback = await client.post(
        BASE + "/webhooks",
        headers=headers(access, str(uuid4())),
        json={
            "name": "ERP receiver regression",
            "url": "https://receiver.example.com/events",
            "events": ["customer.created"],
            "authorization_token": "do-not-leak",
        },
    )
    assert callback.status_code == 201, callback.text
    endpoint = callback.json()["data"]["id"]
    secret = callback.json()["data"]["signing_secret"]
    try:
        visible = await client.get(BASE + "/webhooks", headers=headers(access))
        assert secret not in visible.text and "do-not-leak" not in visible.text
        async with db() as conn:
            transaction = conn.transaction()
            await transaction.start()
            rollback_id = await conn.fetchval(
                "insert into customers(name,notes) values('rollback','secret') returning id::text"
            )
            assert (
                await conn.fetchval(
                    "select count(*) from service_webhook_events where payload->>'resource_id'=$1",
                    rollback_id,
                )
                == 1
            )
            await transaction.rollback()
            assert (
                await conn.fetchval(
                    "select count(*) from service_webhook_events where payload->>'resource_id'=$1",
                    rollback_id,
                )
                == 0
            )
        created = await client.post(
            "/api/v1/customers",
            headers=headers(access),
            json={"name": "Webhook customer", "notes": "NEVER SEND THIS"},
        )
        assert created.status_code == 200, created.text
        resource = created.json()["data"]["id"]
        async with db() as conn:
            row = await conn.fetchrow(
                "select d.id::text,d.event_id::text,v.payload from service_webhook_deliveries d "
                "join service_webhook_events v on v.id=d.event_id where d.endpoint_id=$1::uuid "
                "and v.payload->>'resource_id'=$2",
                endpoint,
                resource,
            )
            assert (
                row
                and "NEVER SEND THIS" not in str(row["payload"])
                and "Webhook customer" not in str(row["payload"])
            )
            await conn.execute(
                "update service_webhook_endpoints set active=false where id=$1::uuid", endpoint
            )
        assert await webhooks.claim_delivery(current.context) is None
        async with db() as conn:
            assert (
                await conn.fetchval(
                    "select state from service_webhook_deliveries where id=$1::uuid", row["id"]
                )
                == "pending"
            )
            await conn.execute(
                "update service_webhook_endpoints set active=true where id=$1::uuid", endpoint
            )
        first = await webhooks.claim_delivery(current.context)
        assert first is not None and str(first["id"]) == row["id"]
        assert await webhooks.claim_delivery(current.context) is None
        async with db() as conn:
            await conn.execute(
                "update service_webhook_deliveries set lease_until=now()-interval '1 second' where id=$1::uuid",
                row["id"],
            )
        second = await webhooks.claim_delivery(current.context)
        assert second and second["lease_id"] != first["lease_id"]
        await webhooks.finish_delivery(current.context, first, status=200, error=None)
        async with db() as conn:
            assert (
                await conn.fetchval(
                    "select state from service_webhook_deliveries where id=$1::uuid", row["id"]
                )
                == "sending"
            )
        await webhooks.finish_delivery(current.context, second, status=500, error="http_500")
        async with db() as conn:
            assert (
                await conn.fetchval(
                    "select state from service_webhook_deliveries where id=$1::uuid", row["id"]
                )
                == "pending"
            )
            await conn.execute(
                "update service_webhook_deliveries set available_at=now() where id=$1::uuid",
                row["id"],
            )

        async def delivered(delivery: Any, context: Any):
            assert str(delivery["event_id"]) == row["event_id"]
            return 204, None

        monkeypatch.setattr(webhooks, "send_delivery", delivered)
        assert (await webhooks.drain(current.context))["processed"] == 1
        assert (await webhooks.drain(current.context))["processed"] == 0
        attempts = await client.get(
            BASE + f"/deliveries/{row['id']}/attempts", headers=headers(access)
        )
        assert attempts.status_code == 200 and len(attempts.json()["data"]) == 3
    finally:
        async with db() as conn:
            await conn.execute("delete from service_webhook_endpoints where id=$1::uuid", endpoint)


def test_webhook_tasks_load_with_celery_and_use_isolated_queue():
    celery_app.loader.import_default_modules()
    assert "app.workers.integration_tasks.sweep" in celery_app.tasks
    assert "app.workers.integration_tasks.deliver" in celery_app.tasks
    assert (
        celery_app.conf.beat_schedule["integration-services-sweep"]["options"]["queue"]
        == "webhooks"
    )


async def test_expired_and_disabled_owner_tokens_fail_closed(client: httpx.AsyncClient):
    access = (await tenant_login(client))["access_token"]
    issued = await issue(client, access, ["customers.read"])
    async with db() as connection:
        await connection.execute(
            "update users set is_active=false where id=$1::uuid", issued["owner_id"]
        )
        try:
            assert (
                await client.get("/api/v1/customers", headers=headers(issued["token"]))
            ).status_code == 401
        finally:
            await connection.execute(
                "update users set is_active=true where id=$1::uuid", issued["owner_id"]
            )
        await connection.execute(
            "update service_api_tokens set expires_at=now()-interval '1 second' where id=$1::uuid",
            issued["id"],
        )
        assert (
            await client.get("/api/v1/customers", headers=headers(issued["token"]))
        ).status_code == 401


async def test_completed_idempotency_keys_survive_history_cleanup(client: httpx.AsyncClient):
    current = await tenant_identity()
    key = str(uuid4())
    fingerprint = ledger.request_fingerprint(
        "POST", "/api/v1/customers", "", "application/json", b"{}"
    )
    reservation = await ledger.reserve(current, key, fingerprint, "POST", "/api/v1/customers")
    await ledger.complete(current, reservation.id, 201, [], b"{}")
    async with db() as connection:
        await connection.execute(
            "update service_api_requests set created_at=now()-interval '100 days' where id=$1::uuid",
            reservation.id,
        )
    await webhooks.cleanup(current.context)
    with pytest.raises(APIError) as failure:
        await ledger.reserve(current, key, fingerprint, "POST", "/api/v1/customers")
    assert failure.value.code == "IDEMPOTENCY_REPLAY_EXPIRED"


async def test_platform_token_never_inherits_additional_tenant_grants(client: httpx.AsyncClient):
    access = (await platform_login_with_second_factor(client))["access_token"]
    issued = await issue(client, access, ["tenants.read"], platform=True)
    async with integration_session(None) as session:
        await session.execute(
            text("update service_api_tokens set tenant_ids='[]'::jsonb where id=cast(:id as uuid)"),
            {"id": issued["id"]},
        )
        await session.commit()
    try:
        response = await client.get("/api/v1/platform/tenants", headers=headers(issued["token"]))
        assert response.status_code == 200 and response.json()["data"] == []
    finally:
        await client.delete(
            PLATFORM + f"/tokens/{issued['id']}", headers=headers(access, str(uuid4()))
        )


async def test_appointment_status_and_reschedule_keep_generic_update_event(
    client: httpx.AsyncClient,
):
    async with db() as connection:
        transaction = connection.transaction()
        await transaction.start()
        try:
            owner = await connection.fetchval(
                "select id from users where email=$1", settings.dev_tenant_admin_email
            )
            await connection.execute(
                "insert into service_webhook_endpoints(name,url,events,secret_ref,created_by) "
                "values('transactional event test','https://example.com/events','[\"*\"]'::jsonb,'test-only',$1)",
                owner,
            )
            customer = await connection.fetchval(
                "insert into customers(name) values('private test customer') returning id"
            )
            service = await connection.fetchval(
                "insert into services(name) values('private test service') returning id"
            )
            professional = await connection.fetchval(
                "insert into professionals(name) values('private test professional') returning id"
            )
            appointment = await connection.fetchval(
                "insert into appointments(customer_id,service_id,professional_id,starts_at,ends_at) "
                "values($1,$2,$3,now()+interval '100 days',now()+interval '100 days 30 minutes') returning id",
                customer,
                service,
                professional,
            )
            await connection.execute(
                "update appointments set status='CONFIRMED' where id=$1", appointment
            )
            events = [
                row["event_type"]
                for row in await connection.fetch(
                    "select event_type from service_webhook_events where payload->>'resource_id'=$1",
                    str(appointment),
                )
            ]
            assert sorted(events) == [
                "appointment.confirmed",
                "appointment.created",
                "appointment.updated",
            ]
            await connection.execute(
                "update appointments set starts_at=starts_at+interval '1 day',ends_at=ends_at+interval '1 day' where id=$1",
                appointment,
            )
            events = [
                row["event_type"]
                for row in await connection.fetch(
                    "select event_type from service_webhook_events where payload->>'resource_id'=$1",
                    str(appointment),
                )
            ]
            assert events.count("appointment.rescheduled") == 1
            assert events.count("appointment.updated") == 2
        finally:
            await transaction.rollback()
