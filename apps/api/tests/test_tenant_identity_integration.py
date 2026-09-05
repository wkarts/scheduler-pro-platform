"""Identity isolation and authorization with real PostgreSQL/MinIO; SMTP captured, not sent."""

import io
import re
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from app.integration_services.auth import integration_session
from app.services.tenant_mail_service import TenantMailService
from app.services.password_recovery_service import TenantPasswordRecoveryService
from app.services.tenant_resolver import TenantResolver
from test_foundation_integration import tenant_login, _prepare_second_tenant
from test_integration_services_integration import db, issue

pytestmark = pytest.mark.integration
BASE = "/api/v1/access"
PASSWORD = "Identity-secure-pass-2099"


def auth(token):
    return {"authorization": f"Bearer {token}"}


async def admin(client):
    value = await tenant_login(client)
    return value["access_token"]


@pytest.fixture
def messages(monkeypatch):
    from app.services.tenant_mail_service import TenantSmtpConfig

    config = TenantSmtpConfig(
        True,
        "smtp.example.invalid",
        587,
        "",
        "",
        "sender@example.com",
        "Scheduler",
        "",
        True,
        False,
        5,
    )
    monkeypatch.setattr(TenantMailService, "config", AsyncMock(return_value=config))
    monkeypatch.setattr(TenantMailService, "_delivery_mode", AsyncMock(return_value="tenant"))
    captured = []
    monkeypatch.setattr(
        TenantMailService,
        "_send_sync",
        staticmethod(lambda c, to, subject, body: captured.append((to, body))),
    )
    return captured


async def group(client, token, keys):
    response = await client.post(
        BASE + "/groups",
        headers=auth(token),
        json={"name": f"Group {uuid4().hex}", "permissions": keys},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


async def new_user(client, token, messages, keys=(), professional_id=None):
    gids = [await group(client, token, list(keys))] if keys else []
    email = f"identity-{uuid4().hex}@example.com"
    response = await client.post(
        BASE + "/users",
        headers=auth(token),
        json={
            "display_name": "Identity user",
            "email": email,
            "group_ids": gids,
            "professional_id": professional_id,
        },
    )
    assert response.status_code == 201, response.text
    value = response.json()["data"]
    assert value["invitation_sent"] is True
    raw = re.search(r"token=([\w-]+)", messages[-1][1])[1]
    return value, raw


async def accept(client, raw):
    response = await client.post(
        BASE + "/confirm-email", json={"token": raw, "new_password": PASSWORD}
    )
    assert response.status_code == 200, response.text


async def login_user(client, email, password=PASSWORD):
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_iam_invite_pending_hash_expiry_single_use_and_legacy_accounts(client, messages):
    token = await admin(client)
    catalog = await client.get(BASE + "/catalog", headers=auth(token))
    assert catalog.status_code == 200, catalog.text
    assert "users.manage" in catalog.json()["data"]["actor_permissions"]
    before = await client.get(BASE + "/profile", headers=auth(token))
    assert not before.json()["data"]["verification_required"]
    user, raw = await new_user(client, token, messages)
    denied = await client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": PASSWORD}
    )
    assert denied.status_code == 401
    async with db() as conn:
        stored = await conn.fetchval(
            "select token_hash from identity_email_tokens where user_id=$1::uuid", user["id"]
        )
        assert stored and raw not in stored
        await conn.execute(
            "update identity_email_tokens set expires_at=now()-interval '1 second' where user_id=$1::uuid",
            user["id"],
        )
    assert (
        await client.post(BASE + "/confirm-email", json={"token": raw, "new_password": PASSWORD})
    ).status_code == 400
    async with db() as conn:
        await conn.execute(
            "update identity_email_tokens set expires_at=now()+interval '1 hour' where user_id=$1::uuid",
            user["id"],
        )
    await accept(client, raw)
    assert (
        await client.post(BASE + "/confirm-email", json={"token": raw, "new_password": PASSWORD})
    ).status_code == 400
    login = await login_user(client, user["email"])
    assert login["user"]["permissions"] == []
    profile = await client.get(BASE + "/profile", headers=auth(login["access_token"]))
    assert (
        profile.status_code == 200
        and profile.json()["data"]["email_verified_at"]
        and profile.json()["data"]["last_login_at"]
    )
    assert profile.json()["data"]["professional_id"] is None


async def test_iam_delegation_self_mutation_foreign_group_and_mass_assignment(client, messages):
    root = await admin(client)
    low, _raw = await new_user(
        client, root, messages, ["users.read", "users.manage", "groups.manage", "customers.read"]
    )
    await accept(client, _raw)
    login = await login_user(client, low["email"])
    h = auth(login["access_token"])
    bad = await client.post(
        BASE + "/groups", headers=h, json={"name": "Escalate", "permissions": ["tenant.manage"]}
    )
    assert bad.status_code == 403, bad.text
    root_profile = (await client.get(BASE + "/profile", headers=auth(root))).json()["data"]
    data = {"display_name": "Changed", "is_active": True, "group_ids": []}
    assert (await client.put(BASE + f"/users/{low['id']}", headers=h, json=data)).status_code == 403
    assert (
        await client.put(BASE + f"/users/{root_profile['id']}", headers=h, json=data)
    ).status_code == 403
    attempt = await client.post(
        BASE + "/users",
        headers=h,
        json={
            "display_name": "Escalation",
            "email": f"{uuid4()}@example.com",
            "group_ids": [root_profile["groups"][0]["id"]],
        },
    )
    assert attempt.status_code == 403, attempt.text
    attempt = await client.post(
        BASE + "/users",
        headers=auth(root),
        json={
            "display_name": "Missing group",
            "email": f"{uuid4()}@example.com",
            "group_ids": [str(uuid4())],
        },
    )
    assert attempt.status_code == 404, attempt.text
    assert (
        await client.put(
            BASE + "/profile", headers=h, json={"display_name": "Override", "group_ids": []}
        )
    ).status_code == 422
    assert (await client.get(BASE + "/audit", headers=h)).status_code == 403


async def test_iam_inactive_groups_affect_jwt_and_existing_machine_tokens(client, messages):
    root = await admin(client)
    user, raw = await new_user(client, root, messages, ["customers.read"])
    await accept(client, raw)
    login = await login_user(client, user["email"])
    access = login["access_token"]
    machine = await issue(client, access, ["customers.read"])
    assert (await client.get("/api/v1/customers", headers=auth(access))).status_code == 200
    gid = user["groups"][0]["id"]
    result = await client.put(
        BASE + f"/groups/{gid}",
        headers=auth(root),
        json={"name": f"Disabled {uuid4()}", "permissions": ["customers.read"], "is_active": False},
    )
    assert result.status_code == 200, result.text
    assert (await client.get("/api/v1/customers", headers=auth(access))).status_code == 403
    assert (
        await client.get("/api/v1/customers", headers=auth(machine["token"]))
    ).status_code == 403
    assert (await client.get(BASE + "/profile", headers=auth(access))).status_code == 200


async def test_iam_deactivation_and_password_change_revoke_sessions_and_api_tokens(
    client, messages
):
    root = await admin(client)
    user, raw = await new_user(client, root, messages, ["customers.read"])
    await accept(client, raw)
    login = await login_user(client, user["email"])
    access = login["access_token"]
    machine = await issue(client, access, ["customers.read"])
    changed = await client.post(
        BASE + "/profile/password",
        headers=auth(access),
        json={"current_password": PASSWORD, "new_password": PASSWORD + "New"},
    )
    assert changed.status_code == 200, changed.text
    assert (await client.get(BASE + "/profile", headers=auth(access))).status_code == 401
    assert (
        await client.get("/api/v1/customers", headers=auth(machine["token"]))
    ).status_code == 401
    login = await login_user(client, user["email"], PASSWORD + "New")
    result = await client.put(
        BASE + f"/users/{user['id']}",
        headers=auth(root),
        json={
            "display_name": user["display_name"],
            "group_ids": [g["id"] for g in user["groups"]],
            "is_active": False,
        },
    )
    assert result.status_code == 200, result.text
    assert (
        await client.get(BASE + "/profile", headers=auth(login["access_token"]))
    ).status_code == 401


async def test_iam_last_administrator_cannot_be_removed_and_rolls_back(client):
    access = await admin(client)
    profile = (await client.get(BASE + "/profile", headers=auth(access))).json()["data"]
    groups = (await client.get(BASE + "/groups", headers=auth(access))).json()["data"]
    own = next(
        g
        for g in groups
        if g["id"] in {x["id"] for x in profile["groups"]} and "tenant.manage" in g["permissions"]
    )
    result = await client.put(
        BASE + f"/groups/{own['id']}",
        headers=auth(access),
        json={"name": own["name"], "permissions": [], "is_active": False},
    )
    assert result.status_code == 409, result.text
    after = (await client.get(BASE + "/profile", headers=auth(access))).json()["data"]
    assert "users.manage" in after["permissions"] and "tenant.manage" in after["permissions"]


async def test_iam_optional_professional_isolated_and_one_to_one(client, messages):
    access = await admin(client)
    async with db() as conn:
        pid = str(
            await conn.fetchval(
                "insert into professionals(name) values('IAM professional') returning id"
            )
        )
    user, raw = await new_user(client, access, messages, professional_id=pid)
    assert user["permissions"] == [] and user["professional_id"] == pid
    attempt = await client.post(
        BASE + "/users",
        headers=auth(access),
        json={
            "display_name": "Duplicate link",
            "email": f"{uuid4()}@example.com",
            "professional_id": pid,
        },
    )
    assert attempt.status_code == 409, attempt.text
    attempt = await client.post(
        BASE + "/users",
        headers=auth(access),
        json={
            "display_name": "Wrong link",
            "email": f"{uuid4()}@example.com",
            "professional_id": str(uuid4()),
        },
    )
    assert attempt.status_code == 404, attempt.text
    result = await client.put(
        BASE + f"/users/{user['id']}",
        headers=auth(access),
        json={"display_name": user["display_name"], "professional_id": None, "group_ids": []},
    )
    assert result.status_code == 200, result.text
    async with db() as conn:
        assert (
            await conn.fetchval("select name from professionals where id=$1::uuid", pid)
            == "IAM professional"
        )


async def test_iam_cross_tenant_tokens_links_and_profile_data(client, messages):
    access = await admin(client)
    user, raw = await new_user(client, access, messages)
    await accept(client, raw)
    login = await login_user(client, user["email"])
    domain, other_email, other_password, _ = await _prepare_second_tenant()
    foreign = await client.get(
        BASE + "/profile", headers={**auth(login["access_token"]), "host": domain}
    )
    assert foreign.status_code == 403, foreign.text
    other = await client.post(
        "/api/v1/auth/login",
        headers={"host": domain},
        json={"email": other_email, "password": other_password},
    )
    assert other.status_code == 200, other.text
    other_profile = await client.get(
        BASE + "/profile", headers={"host": domain, **auth(other.json()["data"]["access_token"])}
    )
    assert other_profile.status_code == 200 and other_profile.json()["data"]["id"] != user["id"]
    second, newraw = await new_user(client, access, messages)
    assert (
        await client.post(
            BASE + "/confirm-email",
            headers={"host": domain},
            json={"token": newraw, "new_password": PASSWORD},
        )
    ).status_code == 400
    await accept(client, newraw)


async def test_iam_email_change_needs_password_and_new_inbox_confirmation(client, messages):
    root = await admin(client)
    user, raw = await new_user(client, root, messages)
    await accept(client, raw)
    login = await login_user(client, user["email"])
    access = login["access_token"]
    new = f"changed-{uuid4().hex}@example.com"
    denied = await client.post(
        BASE + "/profile/email",
        headers=auth(access),
        json={"email": new, "current_password": "incorrect"},
    )
    assert denied.status_code == 403
    async with db() as conn:
        await conn.execute(
            "update identity_email_tokens set created_at=now()-interval '2 minutes' where user_id=$1::uuid",
            user["id"],
        )
    result = await client.post(
        BASE + "/profile/email",
        headers=auth(access),
        json={"email": new, "current_password": PASSWORD},
    )
    assert result.status_code == 200, result.text
    assert (await client.get(BASE + "/profile", headers=auth(access))).json()["data"][
        "email"
    ] == user["email"]
    change = re.search(r"token=([\w-]+)", messages[-1][1])[1]
    assert messages[-1][0] == new
    result = await client.post(BASE + "/confirm-email", json={"token": change})
    assert result.status_code == 200, result.text
    assert (await client.get(BASE + "/profile", headers=auth(access))).status_code == 401
    await login_user(client, new)


async def test_iam_photo_real_minio_private_reencoding_and_removal(client, messages):
    root = await admin(client)
    user, raw = await new_user(client, root, messages)
    await accept(client, raw)
    login = await login_user(client, user["email"])
    h = auth(login["access_token"])
    pic = io.BytesIO()
    Image.new("RGB", (800, 600), "red").save(pic, "PNG")
    response = await client.put(
        BASE + "/profile/avatar", headers={**h, "content-type": "image/png"}, content=pic.getvalue()
    )
    assert response.status_code == 200, response.text
    response = await client.get(BASE + "/profile/avatar", headers=h)
    assert response.status_code == 200, response.text
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (512, 384)
    async with db() as conn:
        key = await conn.fetchval("select avatar_key from users where id=$1::uuid", user["id"])
    assert (await client.get("/api/v1/files/content/" + key, headers=auth(root))).status_code == 403
    assert (
        await client.put(
            BASE + "/profile/avatar",
            headers={**h, "content-type": "image/svg+xml"},
            content=b"<svg/>",
        )
    ).status_code == 415
    assert (await client.delete(BASE + "/profile/avatar", headers=h)).status_code == 200
    assert (await client.get(BASE + "/profile/avatar", headers=h)).status_code == 404


async def test_iam_password_recovery_reuses_existing_flow_and_revokes_api(client, messages):
    root = await admin(client)
    user, raw = await new_user(client, root, messages, ["customers.read"])
    await accept(client, raw)
    login = await login_user(client, user["email"])
    machine = await issue(client, login["access_token"], ["customers.read"])
    async with integration_session(None) as session:
        context = await TenantResolver(session).resolve("localhost")
    async with integration_session(context) as session:
        created = await TenantPasswordRecoveryService(session).create_reset_token(
            user["email"], ip_address=None, correlation_id=None
        )
        assert created
    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={"token": created[1], "new_password": PASSWORD + "Reset"},
    )
    assert reset.status_code == 200, reset.text
    assert (
        await client.get("/api/v1/customers", headers=auth(machine["token"]))
    ).status_code == 401
    await login_user(client, user["email"], PASSWORD + "Reset")


async def test_iam_smtp_failure_preserves_pending_account_and_no_privileges(
    client, monkeypatch, messages
):
    root = await admin(client)

    def fail(*args):
        raise RuntimeError("simulated delivery failure")

    monkeypatch.setattr(TenantMailService, "_send_sync", staticmethod(fail))
    email = f"pending-{uuid4().hex}@example.com"
    response = await client.post(
        BASE + "/users",
        headers=auth(root),
        json={"display_name": "Pending delivery", "email": email},
    )
    assert response.status_code == 201, response.text
    user = response.json()["data"]
    assert user["invitation_sent"] is False and user["verification_required"] is True
    assert user["permissions"] == []
    assert (await client.get(BASE + f"/users/{user['id']}", headers=auth(root))).status_code == 200
    duplicate = await client.post(
        BASE + "/users",
        headers=auth(root),
        json={"display_name": "Duplicate", "email": email.upper()},
    )
    assert duplicate.status_code == 409


async def test_iam_parallel_invite_redemption_has_one_winner(client, messages):
    import asyncio

    root = await admin(client)
    user, raw = await new_user(client, root, messages)
    responses = await asyncio.gather(
        *[
            client.post(BASE + "/confirm-email", json={"token": raw, "new_password": PASSWORD})
            for _ in range(2)
        ]
    )
    assert sorted(r.status_code for r in responses) == [200, 400], [r.text for r in responses]
    await login_user(client, user["email"])


async def test_iam_profile_rejects_foreign_storage_key_and_group_assignment(client, messages):
    root = await admin(client)
    user, raw = await new_user(client, root, messages)
    await accept(client, raw)
    access = (await login_user(client, user["email"]))["access_token"]
    for field, value in [
        ("avatar_key", "_identity/another/file.png"),
        ("group_ids", [str(uuid4())]),
        ("is_active", True),
        ("professional_id", str(uuid4())),
    ]:
        result = await client.put(
            BASE + "/profile",
            headers=auth(access),
            json={"display_name": "Safe name", field: value},
        )
        assert result.status_code == 422, result.text
    changed = await client.put(
        BASE + "/profile",
        headers=auth(access),
        json={"display_name": "Safe name", "phone": "5575999991111"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["permissions"] == []
    audit = await client.get(BASE + "/audit", headers=auth(root))
    assert audit.status_code == 200 and raw not in audit.text and PASSWORD not in audit.text
