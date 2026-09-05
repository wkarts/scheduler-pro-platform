"""Real tenant databases and MinIO; only outbound email delivery is intercepted."""

import asyncio
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import httpx
from PIL import Image
from sqlalchemy import text
import pytest

from app.core.security import hash_password
from app.identity.service import TenantIdentityService
from app.integration_services.auth import integration_session
from app.services.tenant_resolver import TenantResolver
from test_foundation_integration import tenant_login, _prepare_second_tenant
from test_integration_services_integration import db, headers, issue

pytestmark = pytest.mark.integration
BASE = "/api/v1/access"
PASSWORD = "Person-Valid-Password-2026!"


@pytest.fixture
def mail(monkeypatch):
    sent = []

    async def send(self, email, token, purpose):
        sent.append((email, token, purpose))
        return True

    monkeypatch.setattr(TenantIdentityService, "send_link", send)
    return sent


async def group(client, access, permissions):
    response = await client.post(
        BASE + "/groups",
        headers=headers(access),
        json={
            "name": "Grupo " + uuid4().hex,
            "description": "Integration regression",
            "permissions": permissions,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def person(client, access, mail, groups=(), professional=None, verified=True):
    email = uuid4().hex + "@example.com"
    result = await client.post(
        BASE + "/users",
        headers=headers(access),
        json={
            "email": email,
            "display_name": "Pessoa de teste",
            "group_ids": list(groups),
            "professional_id": professional,
        },
    )
    assert result.status_code == 201, result.text
    user = result.json()["data"]
    assert "password_hash" not in result.text and "token_hash" not in result.text
    assert user["professional_id"] == professional
    if verified:
        response = await client.post(
            BASE + "/confirm-email", json={"token": mail[-1][1], "new_password": PASSWORD}
        )
        assert response.status_code == 200, response.text
    return user


async def login_person(client, user, password=PASSWORD, host="localhost"):
    response = await client.post(
        "/api/v1/auth/login",
        headers={"host": host},
        json={"email": user["email"], "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def update_payload(user, **changes):
    return {
        "display_name": user["display_name"],
        "phone": None,
        "is_active": True,
        "professional_id": user["professional_id"],
        "group_ids": [g["id"] for g in user["groups"]],
        **changes,
    }


async def test_legacy_users_and_invitation_verification_expiry_single_use(
    client: httpx.AsyncClient, mail
):
    admin = await tenant_login(client)
    access = admin["access_token"]
    old = await client.get(BASE + "/profile", headers=headers(access))
    assert old.status_code == 200 and old.json()["data"]["last_login_at"]
    user = await person(client, access, mail, verified=False)
    raw = mail[-1][1]
    async with db() as conn:
        stored = await conn.fetchrow(
            "select token_hash from identity_email_tokens where user_id=$1::uuid and used_at is null",
            user["id"],
        )
        assert stored["token_hash"] == sha256(raw.encode()).hexdigest()
        await conn.execute(
            "update users set password_hash=$1 where id=$2::uuid",
            hash_password(PASSWORD),
            user["id"],
        )
    denied = await client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": PASSWORD}
    )
    assert (
        denied.status_code == 403
        and denied.json()["error"]["code"] == "AUTH_EMAIL_VERIFICATION_REQUIRED"
    )
    invalid = await client.post(
        BASE + "/confirm-email", json={"token": raw, "new_password": "short"}
    )
    assert invalid.status_code == 422
    confirmed = await client.post(
        BASE + "/confirm-email", json={"token": raw, "new_password": PASSWORD}
    )
    assert confirmed.status_code == 200, confirmed.text
    reused = await client.post(
        BASE + "/confirm-email", json={"token": raw, "new_password": PASSWORD}
    )
    assert reused.status_code == 400
    auth = await login_person(client, user)
    profile = await client.get(BASE + "/profile", headers=headers(auth["access_token"]))
    assert profile.json()["data"]["email_verified_at"] and profile.json()["data"]["groups"] == []
    expired = await person(client, access, mail, verified=False)
    async with db() as conn:
        await conn.execute(
            "update identity_email_tokens set expires_at=now()-interval '1 second' where user_id=$1::uuid",
            expired["id"],
        )
    assert (
        await client.post(
            BASE + "/confirm-email", json={"token": mail[-1][1], "new_password": PASSWORD}
        )
    ).status_code == 400
    assert (await client.get(BASE + "/confirm-page")).headers.get("content-security-policy")


async def test_group_delegation_mass_assignment_last_admin_and_self_protection(client, mail):
    admin = await tenant_login(client)
    access = admin["access_token"]
    limited = await group(
        client, access, ["users.read", "users.manage", "groups.manage", "customers.read"]
    )
    user = await person(client, access, mail, [limited["id"]])
    auth = await login_person(client, user)
    low = auth["access_token"]
    escalate = await client.post(
        BASE + "/groups",
        headers=headers(low),
        json={"name": "Escalada", "permissions": ["tenant.manage"]},
    )
    assert escalate.status_code == 403, escalate.text
    admin_profile = (await client.get(BASE + "/profile", headers=headers(access))).json()["data"]
    own = await client.put(
        BASE + "/users/" + user["id"], headers=headers(low), json=update_payload(user)
    )
    assert own.status_code == 409
    target = await client.put(
        BASE + "/users/" + admin_profile["id"],
        headers=headers(low),
        json=update_payload(admin_profile, is_active=False),
    )
    assert target.status_code == 403
    mass = await client.put(
        BASE + "/profile", headers=headers(low), json={"display_name": "Changed", "is_active": True}
    )
    assert mass.status_code == 422
    # Remove the auxiliary admin first, then the sole remaining administrator's group cannot be disabled.
    assert (
        await client.put(
            BASE + "/users/" + user["id"],
            headers=headers(access),
            json=update_payload(user, is_active=False),
        )
    ).status_code == 200
    full_groups = (await client.get(BASE + "/groups", headers=headers(access))).json()["data"]
    admin_group = next(
        g
        for g in full_groups
        if g["id"] in {x["id"] for x in admin_profile["groups"]}
        and "users.manage" in g["permissions"]
    )
    result = await client.put(
        BASE + "/groups/" + admin_group["id"],
        headers=headers(access),
        json={k: admin_group[k] for k in ["name", "description", "permissions"]}
        | {"is_active": False},
    )
    assert result.status_code == 409 and result.json()["error"]["code"] == "IAM_LAST_ADMIN", (
        result.text
    )
    assert (await client.get(BASE + "/profile", headers=headers(access))).status_code == 200


async def test_live_group_permissions_disable_reactivation_and_api_token_ceiling(client, mail):
    admin = await tenant_login(client)
    access = admin["access_token"]
    # Issuance is an administrative operation, distinct from consuming customers.read.
    role = await group(client, access, ["customers.read", "tenant.manage"])
    user = await person(client, access, mail, [role["id"]])
    login = await login_person(client, user)
    bearer = login["access_token"]
    token = (await issue(client, bearer, ["customers.read"]))["token"]
    assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 200
    change = {
        "name": role["name"],
        "description": "",
        "permissions": role["permissions"],
        "is_active": False,
    }
    assert (
        await client.put(BASE + "/groups/" + role["id"], headers=headers(access), json=change)
    ).status_code == 200
    assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 403
    assert (await client.get("/api/v1/customers", headers=headers(bearer))).status_code == 403
    # Profile stays accessible; disabling a group is not disabling the user.
    assert (await client.get(BASE + "/profile", headers=headers(bearer))).status_code == 200
    assert (
        await client.put(
            BASE + "/groups/" + role["id"],
            headers=headers(access),
            json=change | {"is_active": True},
        )
    ).status_code == 200
    assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 200
    assert (
        await client.put(
            BASE + "/users/" + user["id"],
            headers=headers(access),
            json=update_payload(user, is_active=False),
        )
    ).status_code == 200
    assert (await client.get(BASE + "/profile", headers=headers(bearer))).status_code == 401
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    ).status_code == 401
    assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 401
    assert (
        await client.put(
            BASE + "/users/" + user["id"], headers=headers(access), json=update_payload(user)
        )
    ).status_code == 200
    assert (await client.get("/api/v1/customers", headers=headers(token))).status_code == 401
    new = await login_person(client, user)
    assert (
        await client.get(BASE + "/profile", headers=headers(new["access_token"]))
    ).status_code == 200
    assert (await client.get(BASE + "/users", headers=headers(token))).status_code in {401, 403}


async def test_optional_professional_link_and_cross_tenant_isolation(client, mail):
    admin = await tenant_login(client)
    access = admin["access_token"]
    async with db() as conn:
        professional = str(
            await conn.fetchval(
                "insert into professionals(name) values($1) returning id",
                "Pessoa sem conta " + uuid4().hex,
            )
        )
    user = await person(client, access, mail, professional=professional)
    auth = await login_person(client, user)
    profile = (await client.get(BASE + "/profile", headers=headers(auth["access_token"]))).json()[
        "data"
    ]
    assert profile["professional_id"] == professional and profile["permissions"] == []
    another = await person(client, access, mail)
    assert (
        await client.put(
            BASE + "/users/" + another["id"],
            headers=headers(access),
            json=update_payload(another, professional_id=professional),
        )
    ).status_code == 409
    assert (
        await client.put(
            BASE + "/users/" + another["id"],
            headers=headers(access),
            json=update_payload(another, professional_id=str(uuid4())),
        )
    ).status_code == 422
    host, email_b, password_b, _ = await _prepare_second_tenant()
    other = await login_person(client, {"email": email_b}, password=password_b, host=host)
    # Tenant B's shared fixture deliberately grants only customer permissions.
    # Add users.read for this check, otherwise a 403 would never exercise the foreign-ID lookup.
    async with integration_session(None) as session:
        context_b = await TenantResolver(session).resolve(host)
    async with integration_session(context_b) as session:
        granted = (
            await session.execute(
                text(
                    "insert into role_permissions(role_id,permission_id) "
                    "select ur.role_id,p.id from user_roles ur join users u on u.id=ur.user_id "
                    "cross join permissions p where u.email=:email and p.key='users.read' "
                    "on conflict do nothing returning role_id,permission_id"
                ),
                {"email": email_b},
            )
        ).all()
        await session.commit()
    try:
        own = await client.get(
            BASE + "/profile", headers={**headers(other["access_token"]), "host": host}
        )
        assert own.status_code == 200 and own.json()["data"]["email"] == email_b
        cross = await client.get(
            BASE + "/users/" + user["id"], headers={**headers(other["access_token"]), "host": host}
        )
        assert cross.status_code == 404, cross.text
    finally:
        async with integration_session(context_b) as session:
            for role_id, permission_id in granted:
                await session.execute(
                    text(
                        "delete from role_permissions where role_id=:role and permission_id=:permission"
                    ),
                    {"role": role_id, "permission": permission_id},
                )
            await session.commit()
    assert (
        await client.get(BASE + "/profile", headers={**headers(auth["access_token"]), "host": host})
    ).status_code == 403
    assert (
        await client.put(
            BASE + "/users/" + user["id"],
            headers=headers(access),
            json=update_payload(user, professional_id=None),
        )
    ).status_code == 200
    async with db() as conn:
        assert (
            await conn.fetchval(
                "select count(*) from professionals where id=$1::uuid", professional
            )
            == 1
        )


async def test_profile_password_and_email_rotation_revoke_credentials(client, mail):
    admin = await tenant_login(client)
    access = admin["access_token"]
    # Issuance is an administrative operation, distinct from consuming customers.read.
    role = await group(client, access, ["customers.read", "tenant.manage"])
    user = await person(client, access, mail, [role["id"]])
    login = await login_person(client, user)
    auth = login["access_token"]
    api_token = (await issue(client, auth, ["customers.read"]))["token"]
    bad = await client.post(
        BASE + "/profile/password",
        headers=headers(auth),
        json={"current_password": "incorrect", "new_password": "Other-Valid-Password-2026!"},
    )
    assert bad.status_code == 403
    update = await client.put(
        BASE + "/profile", headers=headers(auth), json={"display_name": "Novo nome"}
    )
    assert update.status_code == 200 and update.json()["data"]["display_name"] == "Novo nome"
    changed = await client.post(
        BASE + "/profile/password",
        headers=headers(auth),
        json={"current_password": PASSWORD, "new_password": "Other-Valid-Password-2026!"},
    )
    assert changed.status_code == 200, changed.text
    assert (await client.get(BASE + "/profile", headers=headers(auth))).status_code == 401
    assert (await client.get("/api/v1/customers", headers=headers(api_token))).status_code == 401
    login = await login_person(client, user, "Other-Valid-Password-2026!")
    auth = login["access_token"]
    async with db() as conn:
        await conn.execute(
            "update identity_email_tokens set created_at=now()-interval '2 minutes' where user_id=$1::uuid",
            user["id"],
        )
    new_email = uuid4().hex + "@example.com"
    changed = await client.post(
        BASE + "/profile/email",
        headers=headers(auth),
        json={"current_password": "Other-Valid-Password-2026!", "email": new_email},
    )
    assert changed.status_code == 200, changed.text
    assert (await client.get(BASE + "/profile", headers=headers(auth))).json()["data"][
        "email"
    ] == user["email"]
    confirm = await client.post(BASE + "/confirm-email", json={"token": mail[-1][1]})
    assert confirm.status_code == 200, confirm.text
    assert (await client.get(BASE + "/profile", headers=headers(auth))).status_code == 401
    user["email"] = new_email
    await login_person(client, user, "Other-Valid-Password-2026!")


async def test_private_photo_real_minio_validation_and_no_generic_bypass(client, mail):
    admin = await tenant_login(client)
    access = admin["access_token"]
    user = await person(client, access, mail)
    login = await login_person(client, user)
    auth = login["access_token"]
    raw = BytesIO()
    Image.new("RGB", (800, 400), "red").save(raw, format="PNG")
    uploaded = await client.put(
        BASE + "/profile/avatar",
        headers=headers(auth) | {"content-type": "image/png"},
        content=raw.getvalue(),
    )
    assert uploaded.status_code == 200, uploaded.text
    image = await client.get(BASE + "/profile/avatar", headers=headers(auth))
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert "no-store" in image.headers["cache-control"]
    assert Image.open(BytesIO(image.content)).size == (512, 256)
    async with db() as conn:
        key = await conn.fetchval("select avatar_key from users where id=$1::uuid", user["id"])
    denied = await client.get("/api/v1/files/content/" + key, headers=headers(access))
    assert denied.status_code == 403, denied.text
    signed = await client.post(
        "/api/v1/files/signed-url", headers=headers(access), json={"key": key}
    )
    assert signed.status_code == 403
    assert (
        await client.put(BASE + "/profile/avatar", headers=headers(auth), content=b"<svg/>")
    ).status_code == 422
    assert (
        await client.put(
            BASE + "/profile/avatar", headers=headers(auth), content=b"x" * (2 * 1024 * 1024 + 1)
        )
    ).status_code == 413
    assert (await client.delete(BASE + "/profile/avatar", headers=headers(auth))).status_code == 200
    assert (await client.get(BASE + "/profile/avatar", headers=headers(auth))).status_code == 404


async def test_concurrent_duplicate_email_no_ghost_memberships_and_audit(client, mail):
    admin = await tenant_login(client)
    access = admin["access_token"]
    email = uuid4().hex + "@example.com"

    def create(value):
        return client.post(
            BASE + "/users",
            headers=headers(access),
            json={"display_name": "Concorrente", "email": value},
        )

    one, two = await asyncio.gather(create(email), create(email.upper()))
    assert sorted([one.status_code, two.status_code]) == [201, 409], (one.text, two.text)
    created = (one if one.status_code == 201 else two).json()["data"]
    audit = await client.get(BASE + "/audit?user_id=" + created["id"], headers=headers(access))
    assert audit.status_code == 200 and audit.json()["data"]["total"] >= 1
    assert mail[-1][1] not in audit.text and "password_hash" not in audit.text
    limited = await person(client, access, mail)
    login = await login_person(client, limited)
    assert (
        await client.get(BASE + "/audit", headers=headers(login["access_token"]))
    ).status_code == 403
