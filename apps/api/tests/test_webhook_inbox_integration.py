"""Real PostgreSQL/HTTP ingress and indefinite credentials; no external HTTP delivery."""

import asyncio
from hashlib import sha256
import json
import time
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.errors import APIError
from app.identity.policy import revoke_access
from app.integration_services.auth import integration_session
from app.integration_services.config import integration_settings as config
from app.integration_services.webhooks import signature, cleanup
from test_foundation_integration import (
    tenant_login,
    platform_login_with_second_factor,
    _prepare_second_tenant,
)
from test_integration_services_integration import (
    BASE,
    PLATFORM,
    db,
    headers,
    issue,
    tenant_identity,
)

pytestmark = pytest.mark.integration


async def receiver(client, access, *, platform=False, mode="bearer", events=None, rate=120):
    response = await client.post(
        (PLATFORM if platform else BASE) + "/receivers",
        headers=headers(access, str(uuid4())),
        json={
            "name": "Incoming " + uuid4().hex,
            "auth_mode": mode,
            "events": events or ["*"],
            "rate_limit": rate,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def envelope():
    return {
        "id": str(uuid4()),
        "type": "example.changed",
        "data": {"private": "test-only-unique-content", "action": "must_not_execute"},
    }


def signed(secret, event, offset=0):
    raw = json.dumps(event, ensure_ascii=False).encode()
    timestamp = str(int(time.time()) + offset)
    delivery_id = str(uuid4())
    return raw, {
        "content-type": "application/json",
        "x-scheduler-timestamp": timestamp,
        "x-scheduler-delivery-id": delivery_id,
        "x-scheduler-signature": signature(secret, timestamp, delivery_id, raw),
    }


async def test_indefinite_api_credentials_work_for_tenant_and_platform(client):
    for platform in [False, True]:
        access = (
            await (platform_login_with_second_factor(client) if platform else tenant_login(client))
        )["access_token"]
        base = PLATFORM if platform else BASE
        scope = "tenants.read" if platform else "customers.read"
        target = "/api/v1/platform/tenants" if platform else "/api/v1/customers"
        for explicit in [False, True]:
            payload = {"name": "No deadline", "scopes": [scope]}
            if explicit:
                payload["expires_in_days"] = None
            result = await client.post(
                base + "/tokens", headers=headers(access, str(uuid4())), json=payload
            )
            assert result.status_code == 201, result.text
            value = result.json()["data"]
            assert value["expires_at"] is None
            assert (await client.get(target, headers=headers(value["token"]))).status_code == 200
            rotate = await client.post(
                base + "/tokens/" + value["id"] + "/rotate",
                headers=headers(access, str(uuid4())),
                json={},
            )
            assert rotate.status_code == 200 and rotate.json()["data"]["expires_at"] is None, (
                rotate.text
            )
            assert (await client.get(target, headers=headers(value["token"]))).status_code == 401
            revoked = await client.delete(
                base + "/tokens/" + value["id"], headers=headers(access, str(uuid4()))
            )
            assert revoked.status_code == 200
            assert (
                await client.get(target, headers=headers(rotate.json()["data"]["token"]))
            ).status_code == 401


async def test_validity_change_preserves_active_tokens_and_never_revives_expired(client):
    access = (await tenant_login(client))["access_token"]
    new = await client.post(
        BASE + "/tokens",
        headers=headers(access, str(uuid4())),
        json={"name": "Temporary", "scopes": ["customers.read"], "expires_in_days": 30},
    )
    assert new.status_code == 201, new.text
    token = new.json()["data"]
    assert token["expires_at"] is not None
    result = await client.patch(
        BASE + "/tokens/" + token["id"] + "/validity",
        headers=headers(access, str(uuid4())),
        json={"expires_in_days": None},
    )
    assert result.status_code == 200 and result.json()["data"]["expires_at"] is None, result.text
    assert (
        await client.get("/api/v1/customers", headers=headers(token["token"]))
    ).status_code == 200
    result = await client.patch(
        BASE + "/tokens/" + token["id"] + "/validity",
        headers=headers(access, str(uuid4())),
        json={"expires_in_days": 1},
    )
    assert result.status_code == 200 and result.json()["data"]["expires_at"] is not None
    async with db() as conn:
        await conn.execute(
            "update service_api_tokens set expires_at=now()-interval '1 second' where id=$1::uuid",
            token["id"],
        )
    denied = await client.patch(
        BASE + "/tokens/" + token["id"] + "/validity",
        headers=headers(access, str(uuid4())),
        json={"expires_in_days": None},
    )
    assert denied.status_code == 404, denied.text
    assert (
        await client.get("/api/v1/customers", headers=headers(token["token"]))
    ).status_code == 401


async def test_bearer_inbox_is_durable_encrypted_idempotent_and_not_a_command_executor(client):
    access = (await tenant_login(client))["access_token"]
    value = await receiver(client, access)
    assert value["expires_at"] is None
    raw = value["secret"]
    path = value["receive_path"]
    event = envelope()
    assert (await client.post(path, json=event)).status_code == 401
    async with db() as conn:
        before = await conn.fetchval("select count(*) from appointments")
    answers = await asyncio.gather(
        *[client.post(path, headers=headers(raw), json=event) for _ in range(2)]
    )
    assert sorted(r.status_code for r in answers) == [200, 202], [r.text for r in answers]
    assert len({r.json()["data"]["receipt_id"] for r in answers}) == 1
    receipt_id = answers[0].json()["data"]["receipt_id"]
    async with db() as conn:
        row = await conn.fetchrow(
            "select payload_sealed,fingerprint from service_webhook_inbox where id=$1::uuid",
            receipt_id,
        )
        assert event["data"]["private"] not in row["payload_sealed"]
        assert await conn.fetchval("select count(*) from appointments") == before
        stored = await conn.fetchrow(
            "select secret_ref,secret_hash from service_webhook_receivers where id=$1::uuid",
            value["id"],
        )
        assert (
            stored["secret_ref"] is None
            and stored["secret_hash"] == sha256(raw.encode()).hexdigest()
        )
    conflict = await client.post(
        path, headers=headers(raw), json={**event, "data": {"other": True}}
    )
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "WEBHOOK_EVENT_CONFLICT"
    )
    detail = await client.get(BASE + "/inbox/" + receipt_id, headers=headers(access))
    assert detail.status_code == 200 and detail.json()["data"]["event"] == event, detail.text
    assert (await client.get("/api/v1/customers", headers=headers(raw))).status_code == 401
    listing = await client.get(BASE + "/receivers", headers=headers(access))
    assert (
        raw not in listing.text
        and "secret_hash" not in listing.text
        and "secret_ref" not in listing.text
    )
    discarded = await client.delete(
        BASE + "/inbox/" + receipt_id + "/payload", headers=headers(access, str(uuid4()))
    )
    assert discarded.status_code == 409
    reviewed = await client.patch(
        BASE + "/inbox/" + receipt_id + "/status",
        headers=headers(access, str(uuid4())),
        json={"state": "acknowledged"},
    )
    assert reviewed.status_code == 200
    discarded = await client.delete(
        BASE + "/inbox/" + receipt_id + "/payload", headers=headers(access, str(uuid4()))
    )
    assert discarded.status_code == 200 and discarded.json()["data"]["deduplication_preserved"]
    assert (await client.get(BASE + "/inbox/" + receipt_id, headers=headers(access))).json()[
        "data"
    ]["event"] is None
    replay = await client.post(path, headers=headers(raw), json=event)
    assert replay.status_code == 200 and replay.json()["data"]["duplicate"] is True


async def test_hmac_ingress_signature_window_rotation_pause_and_revocation(client):
    access = (await tenant_login(client))["access_token"]
    value = await receiver(client, access, mode="hmac")
    event = envelope()
    for delta in [-400, 400]:
        raw, request_headers = signed(value["secret"], event, delta)
        denied = await client.post(value["receive_path"], headers=request_headers, content=raw)
        assert denied.status_code == 401, denied.text
    raw, request_headers = signed(value["secret"], event)
    denied = await client.post(value["receive_path"], headers=request_headers, content=raw + b" ")
    assert denied.status_code == 401
    accepted = await client.post(value["receive_path"], headers=request_headers, content=raw)
    assert accepted.status_code == 202, accepted.text
    rotate = await client.post(
        BASE + "/receivers/" + value["id"] + "/rotate-secret",
        headers=headers(access, str(uuid4())),
        json={},
    )
    assert rotate.status_code == 200, rotate.text
    assert (
        await client.post(value["receive_path"], headers=request_headers, content=raw)
    ).status_code == 401
    newraw, newheaders = signed(rotate.json()["data"]["secret"], envelope())
    assert (
        await client.post(value["receive_path"], headers=newheaders, content=newraw)
    ).status_code == 202
    for active, expected in [(False, 401), (True, 200)]:
        response = await client.patch(
            BASE + "/receivers/" + value["id"] + "/status",
            headers=headers(access, str(uuid4())),
            json={"active": active},
        )
        assert response.status_code == 200, response.text
        received = await client.post(value["receive_path"], headers=newheaders, content=newraw)
        assert received.status_code == expected, received.text
    revoked = await client.delete(
        BASE + "/receivers/" + value["id"], headers=headers(access, str(uuid4()))
    )
    assert revoked.status_code == 200
    assert (
        await client.post(value["receive_path"], headers=newheaders, content=newraw)
    ).status_code == 401


async def test_incoming_scope_is_bound_to_tenant_and_platform_not_payload(client):
    root = (await tenant_login(client))["access_token"]
    tenant = await receiver(client, root)
    admin = (await platform_login_with_second_factor(client))["access_token"]
    platform = await receiver(client, admin, platform=True)
    host, tenant_id, _, _ = await _prepare_second_tenant()
    event = envelope()
    event["tenant_id"] = tenant_id
    assert (
        await client.post(
            tenant["receive_path"], headers={**headers(tenant["secret"]), "host": host}, json=event
        )
    ).status_code == 401
    assert (
        await client.post(
            platform["receive_path"],
            headers={**headers(platform["secret"]), "host": host},
            json=event,
        )
    ).status_code == 403
    assert (
        await client.post(platform["receive_path"], headers=headers(tenant["secret"]), json=event)
    ).status_code == 401
    result = await client.post(
        tenant["receive_path"], headers=headers(tenant["secret"]), json=event
    )
    assert result.status_code == 202, result.text
    received = await client.post(
        platform["receive_path"], headers=headers(platform["secret"]), json=event
    )
    assert received.status_code == 202, received.text
    assert (
        await client.get(
            PLATFORM + "/inbox/" + result.json()["data"]["receipt_id"], headers=headers(admin)
        )
    ).status_code == 404
    assert (
        await client.get(
            BASE + "/inbox/" + received.json()["data"]["receipt_id"], headers=headers(root)
        )
    ).status_code == 404


async def test_ingress_validates_types_limits_retention_and_disable(client, monkeypatch):
    access = (await tenant_login(client))["access_token"]
    value = await receiver(client, access, events=["example.changed"], rate=120)
    path = value["receive_path"]
    auth = headers(value["secret"])
    event = envelope()
    assert (
        await client.post(path, headers=auth, json={**event, "type": "unexpected"})
    ).status_code == 422
    assert (
        await client.post(path + "?token=not-accepted", headers=auth, json=event)
    ).status_code == 400
    assert (await client.post(path, headers=auth, content=b"{}")).status_code == 415
    with monkeypatch.context() as patch:
        patch.setattr(config, "inbox_max_bytes", 1024)
        assert (
            await client.post(path, headers=auth, json={**event, "data": {"large": "x" * 2048}})
        ).status_code == 413
    with monkeypatch.context() as patch:
        patch.setattr(config, "incoming_webhooks_enabled", False)
        assert (await client.post(path, headers=auth, json=event)).status_code == 503
    accepted = await client.post(path, headers=auth, json=event)
    assert accepted.status_code == 202, accepted.text
    identifier = accepted.json()["data"]["receipt_id"]
    async with db() as conn:
        await conn.execute(
            "update service_webhook_inbox set payload_expires_at=now()-interval '1 second' where id=$1::uuid",
            identifier,
        )
    current = await tenant_identity()
    await cleanup(current.context)
    detail = await client.get(BASE + "/inbox/" + identifier, headers=headers(access))
    assert detail.json()["data"]["event"] is None
    replay = await client.post(path, headers=auth, json=event)
    assert replay.status_code == 200 and replay.json()["data"]["duplicate"]
    async with db() as conn:
        count = await conn.fetchval(
            "select count(*) from service_webhook_inbox where payload_sealed is not null"
        )
    with monkeypatch.context() as patch:
        patch.setattr(config, "inbox_max_payloads", count)
        blocked = await client.post(path, headers=auth, json=envelope())
        assert blocked.status_code == 503, blocked.text
        assert (await client.post(path, headers=auth, json=event)).status_code == 200
    limited = await receiver(client, access, rate=1)
    assert (
        await client.post(
            limited["receive_path"], headers=headers(limited["secret"]), json=envelope()
        )
    ).status_code == 202
    limited_response = await client.post(
        limited["receive_path"], headers=headers(limited["secret"]), json=envelope()
    )
    assert limited_response.status_code == 429 and limited_response.headers["retry-after"] == "60"


async def test_receiver_creation_is_interactive_and_owner_rights_are_live(client, monkeypatch):
    root = (await tenant_login(client))["access_token"]
    token = (
        await issue(client, root, ["integrations.services.read", "integrations.services.write"])
    )["token"]
    blocked = await client.post(
        BASE + "/receivers",
        headers=headers(token, str(uuid4())),
        json={"name": "Undelegated receiver"},
    )
    assert blocked.status_code == 403, blocked.text
    value = await receiver(client, root)
    from app.integration_services import incoming

    async def unavailable(*args, **kwargs):
        raise APIError("API_TOKEN_INVALID", "disabled owner", 401)

    with monkeypatch.context() as patch:
        patch.setattr(incoming, "current_owner", unavailable)
        blocked = await client.post(
            value["receive_path"], headers=headers(value["secret"]), json=envelope()
        )
        assert blocked.status_code == 401, blocked.text
    result = await client.post(
        value["receive_path"], headers=headers(value["secret"]), json=envelope()
    )
    assert result.status_code == 202, result.text
    assert (
        await client.get(
            BASE + "/inbox/" + result.json()["data"]["receipt_id"], headers=headers(token)
        )
    ).status_code == 200


async def test_sensitive_identity_revocation_also_retires_incoming_credentials(client):
    # Roll back the revocation after asserting it; production administrator credentials are not changed.
    access = (await tenant_login(client))["access_token"]
    value = await receiver(client, access)
    identity = await tenant_identity()
    async with integration_session(identity.context) as session:
        await revoke_access(session, identity.principal.user_id)
        revoked = await session.scalar(
            text("select revoked_at from service_webhook_receivers where id=cast(:id as uuid)"),
            {"id": value["id"]},
        )
        assert revoked is not None
        await session.rollback()
    assert (
        await client.post(value["receive_path"], headers=headers(value["secret"]), json=envelope())
    ).status_code == 202
