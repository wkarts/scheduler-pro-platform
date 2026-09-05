"""Consolidated regressions from PR98, using PR99's single identity implementation."""

import asyncio
from uuid import uuid4

import pytest

from app.db.models_platform import Tenant
from app.identity.service import TenantIdentityService
from app.integration_services.auth import integration_session
from app.services.mail_service import mail_delivery
from app.services.password_recovery_service import TenantPasswordRecoveryService
from app.services.tenant_mail_service import TenantMailService
from app.services.tenant_resolver import TenantResolver
from test_foundation_integration import (
    _prepare_second_tenant,
    platform_login_with_second_factor,
    tenant_login,
)
from test_integration_services_integration import db, headers, issue
from test_tenant_identity_integration import BASE, PASSWORD, group, login_person, person

pytestmark = pytest.mark.integration


@pytest.fixture(name="mail")
def capture_identity_mail(monkeypatch):
    sent = []

    async def send(self, email, token, purpose):
        sent.append((email, token, purpose))
        return True

    monkeypatch.setattr(TenantIdentityService, "send_link", send)
    return sent


async def context_for(host="localhost"):
    async with integration_session(None) as session:
        return await TenantResolver(session).resolve(host)


async def test_customer_reader_cannot_issue_machine_tokens(client, mail):
    root = (await tenant_login(client))["access_token"]
    role = await group(client, root, ["customers.read"])
    user = await person(client, root, mail, [role["id"]])
    access = (await login_person(client, user))["access_token"]
    assert (await client.get("/api/v1/customers", headers=headers(access))).status_code == 200
    response = await client.post(
        "/api/v1/integrations/services/tokens",
        headers=headers(access, str(uuid4())),
        json={"name": "Must not be issued", "scopes": ["customers.read"]},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "AUTH_PERMISSION_DENIED"
    async with db() as conn:
        assert (
            await conn.fetchval(
                "select count(*) from service_api_tokens where owner_id=$1::uuid", user["id"]
            )
            == 0
        )


async def test_invitation_is_bound_to_the_issuing_tenant(client, mail):
    root = (await tenant_login(client))["access_token"]
    user = await person(client, root, mail, verified=False)
    raw = mail[-1][1]
    host, _, _, _ = await _prepare_second_tenant()
    response = await client.post(
        BASE + "/confirm-email",
        headers={"host": host},
        json={"token": raw, "new_password": PASSWORD},
    )
    assert response.status_code == 400, response.text
    async with db() as conn:
        assert (
            await conn.fetchval(
                "select verification_required from users where id=$1::uuid", user["id"]
            )
            is True
        )
    valid = await client.post(
        BASE + "/confirm-email", json={"token": raw, "new_password": PASSWORD}
    )
    assert valid.status_code == 200, valid.text
    await login_person(client, user)


async def test_concurrent_invitation_redemption_has_one_winner(client, mail):
    root = (await tenant_login(client))["access_token"]
    user = await person(client, root, mail, verified=False)
    token = mail[-1][1]
    results = await asyncio.gather(
        *[
            client.post(BASE + "/confirm-email", json={"token": token, "new_password": PASSWORD})
            for _ in range(2)
        ]
    )
    assert sorted(result.status_code for result in results) == [200, 400], [r.text for r in results]
    await login_person(client, user)


async def test_existing_password_recovery_revokes_machine_and_browser_access(client, mail):
    root = (await tenant_login(client))["access_token"]
    role = await group(client, root, ["tenant.manage", "customers.read"])
    user = await person(client, root, mail, [role["id"]])
    login = await login_person(client, user)
    token = (await issue(client, login["access_token"], ["customers.read"]))["token"]
    context = await context_for()
    async with integration_session(context) as session:
        reset = await TenantPasswordRecoveryService(session).create_reset_token(
            user["email"],
            ip_address=None,
            correlation_id=None,
        )
        assert reset is not None
    response = await client.post(
        "/api/v1/auth/password/reset", json={"token": reset[1], "new_password": PASSWORD + "Reset"}
    )
    assert response.status_code == 200, response.text
    assert (
        await client.get(BASE + "/profile", headers=headers(login["access_token"]))
    ).status_code == 401
    assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    ).status_code == 401
    await login_person(client, user, PASSWORD + "Reset")


async def test_smtp_failure_keeps_pending_account_without_grants(client, monkeypatch):
    root = (await tenant_login(client))["access_token"]

    def fail(*args, **kwargs):
        raise RuntimeError("simulated SMTP failure")

    # Exercise send_link itself, intercepting only the network boundaries.
    monkeypatch.setattr(TenantMailService, "_send_sync", staticmethod(fail))
    monkeypatch.setattr(mail_delivery, "_send", fail)
    email = uuid4().hex + "@example.com"
    response = await client.post(
        BASE + "/users",
        headers=headers(root),
        json={"display_name": "Awaiting delivery", "email": email},
    )
    assert response.status_code == 201, response.text
    user = response.json()["data"]
    assert user["invitation_sent"] is False and user["verification_required"] is True
    assert not user["email_verified_at"] and user["permissions"] == []
    assert (
        await client.get(BASE + "/users/" + user["id"], headers=headers(root))
    ).status_code == 200
    duplicate = await client.post(
        BASE + "/users",
        headers=headers(root),
        json={"display_name": "Duplicate", "email": email.upper()},
    )
    assert duplicate.status_code == 409


async def test_profile_cannot_assign_foreign_storage_or_privileged_groups(client, mail):
    root = (await tenant_login(client))["access_token"]
    user = await person(client, root, mail)
    access = (await login_person(client, user))["access_token"]
    for field, value in (
        ("avatar_key", "profiles-private/other/person.jpg"),
        ("group_ids", [str(uuid4())]),
        ("professional_id", str(uuid4())),
    ):
        response = await client.put(
            BASE + "/profile",
            headers=headers(access),
            json={"display_name": "Tampered", field: value},
        )
        assert response.status_code == 422, response.text
    profile = (await client.get(BASE + "/profile", headers=headers(access))).json()["data"]
    assert (
        not profile["has_avatar"] and profile["groups"] == [] and profile["professional_id"] is None
    )


@pytest.mark.parametrize("change", ["password", "email"])
async def test_control_plane_recovery_revokes_all_user_credentials(client, mail, change):
    root = (await tenant_login(client))["access_token"]
    # A named custom group works; principal lookup must not depend on 'tenant-admin'.
    role = await group(client, root, ["tenant.manage", "customers.read"])
    user = await person(client, root, mail, [role["id"]])
    login = await login_person(client, user)
    token = (await issue(client, login["access_token"], ["customers.read"]))["token"]
    context = await context_for()
    async with db() as conn:
        await conn.execute(
            "update identity_email_tokens set created_at=now()-interval '2 minutes' where user_id=$1::uuid",
            user["id"],
        )
    pending = await client.post(
        BASE + "/profile/verify-email", headers=headers(login["access_token"])
    )
    assert pending.status_code == 200, pending.text
    email_token = mail[-1][1]
    async with integration_session(context) as session:
        reset = await TenantPasswordRecoveryService(session).create_reset_token(
            user["email"],
            ip_address=None,
            correlation_id=None,
        )
        assert reset is not None
    platform = await platform_login_with_second_factor(client)
    async with integration_session(None) as session:
        tenant = await session.get(Tenant, context.tenant_id)
        assert tenant is not None
        original = dict(tenant.settings or {})
        tenant.settings = {**original, "admin_email": user["email"]}
        await session.commit()
    try:
        payload = {
            change: PASSWORD + "Rotated" if change == "password" else uuid4().hex + "@example.com"
        }
        response = await client.put(
            f"/api/v1/platform/tenant-management/{context.tenant_id}/principal-admin",
            headers=headers(platform["access_token"]),
            json=payload,
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["principal_admin"]["id"] == user["id"]
        assert (
            await client.get(BASE + "/profile", headers=headers(login["access_token"]))
        ).status_code == 401
        assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 401
        assert (
            await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
            )
        ).status_code == 401
        assert (
            await client.post(BASE + "/confirm-email", json={"token": email_token})
        ).status_code == 400
        async with db() as conn:
            for table, owner, mark in (
                ("user_sessions", "user_id", "revoked_at"),
                ("refresh_tokens", "user_id", "revoked_at"),
                ("service_api_tokens", "owner_id", "revoked_at"),
                ("password_reset_tokens", "user_id", "used_at"),
                ("identity_email_tokens", "user_id", "used_at"),
            ):
                remaining = await conn.fetchval(
                    f"select count(*) from {table} where {owner}=$1::uuid and {mark} is null",
                    user["id"],
                )
                assert remaining == 0, table
            if change == "email":
                assert (
                    await conn.fetchval(
                        "select email_verified_at from users where id=$1::uuid", user["id"]
                    )
                    is None
                )
        expected_email = payload.get("email", user["email"])
        expected_password = payload.get("password", PASSWORD)
        await login_person(client, {"email": expected_email}, expected_password)
    finally:
        async with integration_session(None) as session:
            tenant = await session.get(Tenant, context.tenant_id)
            assert tenant is not None
            tenant.settings = original
            await session.commit()
