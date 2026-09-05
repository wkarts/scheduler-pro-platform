from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from app.core.errors import APIError
from app.identity.images import MAX_AVATAR_BYTES, normalize_avatar
from app.identity.policy import assert_delegable
from app.identity.schemas import GroupInput, PasswordInput, ProfileInput, UserCreate, UserUpdate
from app.api.v1.routes.files import _ordinary_key


@pytest.mark.parametrize(
    "grants,authority,allowed",
    [
        (set(), set(), True),
        ({"users.read"}, {"users.read"}, True),
        ({"users.manage"}, {"users.read"}, False),
        ({"users.manage", "groups.manage"}, {"users.manage"}, False),
        ({"tenant.manage"}, {"groups.manage", "users.manage"}, False),
    ],
)
def test_delegation_subset(grants, authority, allowed):
    if allowed:
        assert_delegable(grants, authority)
    else:
        with pytest.raises(APIError):
            assert_delegable(grants, authority)


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_avatar_is_decoded_and_normalized(format):
    raw = BytesIO()
    image = Image.new("RGB", (1024, 300), "blue")
    exif = image.getexif()
    exif[270] = "Private EXIF"
    image.save(raw, format=format, exif=exif)
    result = normalize_avatar(raw.getvalue())
    assert b"Private EXIF" not in result
    with Image.open(BytesIO(result)) as photo:
        assert photo.format == "JPEG" and max(photo.size) == 512
        assert not photo.getexif()


@pytest.mark.parametrize(
    "payload", [b'<svg onload="alert(1)"></svg>', b"%PDF-1.7", b"fake image", b""]
)
def test_invalid_photo_rejected(payload):
    with pytest.raises(APIError):
        normalize_avatar(payload)


def test_avatar_dimensions_and_size_limits():
    with pytest.raises(APIError):
        normalize_avatar(b"x" * (MAX_AVATAR_BYTES + 1))
    raw = BytesIO()
    Image.new("RGB", (4097, 1)).save(raw, format="PNG")
    with pytest.raises(APIError):
        normalize_avatar(raw.getvalue())


@pytest.mark.parametrize(
    "key", ["profiles-private/x/y.jpg", "/profiles-private/x/y.jpg", "profiles-private\\x\\y.jpg"]
)
def test_generic_storage_cannot_bypass_profile_authorization(key):
    with pytest.raises(APIError):
        _ordinary_key(key)
    assert _ordinary_key("landing/banner.jpg") == "landing/banner.jpg"


def test_profile_cannot_mass_assign_permissions_email_or_status():
    for name, value in [
        ("email", "admin@example.com"),
        ("is_active", True),
        ("group_ids", []),
        ("professional_id", None),
    ]:
        with pytest.raises(ValidationError):
            ProfileInput.model_validate({"display_name": "Pessoa", name: value})
    data = UserCreate(email="person@example.com", display_name="Pessoa")
    assert data.professional_id is None and data.group_ids == []
    assert (
        PasswordInput(current_password=" a ", new_password=" password 123 ").new_password
        == " password 123 "
    )


def test_ui_has_single_integration_view_and_inline_entity_search():
    root = Path(__file__).resolve().parents[3]
    if not (root / "apps/web").is_dir():
        pytest.skip("Frontend source not present in reduced API image")
    shell = (root / "apps/web/src/TenantConsole.vue").read_text()
    view = (root / "packages/integration-services/IntegrationServicesView.vue").read_text()
    operator = (root / "apps/web/src/TenantAgendaOperator.vue").read_text()
    combo = (root / "packages/ui/EntityCombobox.vue").read_text()
    assert "label: 'Integrações'" in shell and "IntegrationServicesView" in shell
    assert "<dialog" not in view and "<Teleport" not in view and "showModal(" not in view
    assert '<select v-model="selectedServiceId"' not in operator
    assert 'v-model:text="freeService"' in operator and ':allow-custom="true"' in operator
    assert "AbortController" in combo and ".slice(0, 6)" in combo and 'role="combobox"' in combo
    assert "IntegrationServicesLauncher" not in (root / "apps/web/src/main.ts").read_text()
    assert "IntegrationServicesLauncher" not in (root / "apps/admin/src/main.ts").read_text()


@pytest.mark.parametrize(
    "schema,payload",
    [
        (UserCreate, {"display_name": "Teste", "email": "one@example.com", "is_super_admin": True}),
        (GroupInput, {"name": "Teste", "permissions": ["users.read"], "is_super_admin": True}),
        (UserUpdate, {"display_name": "Teste", "is_active": True, "email": "other@example.com"}),
    ],
)
def test_administration_rejects_undeclared_security_fields(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_animated_avatar_is_rejected():
    stream = BytesIO()
    Image.new("RGB", (10, 10), "red").save(
        stream,
        "PNG",
        save_all=True,
        append_images=[Image.new("RGB", (10, 10), "blue")],
        duration=50,
    )
    with pytest.raises(APIError):
        normalize_avatar(stream.getvalue())


def test_avatar_pixel_limit_is_independent_of_dimension_limit():
    stream = BytesIO()
    Image.new("RGB", (4000, 4000)).save(stream, "PNG")
    with pytest.raises(APIError):
        normalize_avatar(stream.getvalue())


def test_identity_routes_cannot_be_delegated_to_machine_tokens():
    from app.integration_services.catalog import scope_for

    for path, method in (
        ("/api/v1/access/profile/password", "POST"),
        ("/api/v1/access/users", "POST"),
    ):
        assert scope_for(path, method, False) is None


def test_new_tenant_bootstrap_and_provisioning_grant_identity_permissions():
    from app.cli import PERMISSIONS
    from app.services.provisioning_runtime import TENANT_ADMIN_PERMISSIONS as provision_permissions

    expected = {"users.read", "users.manage", "groups.manage", "audit.read"}
    assert expected <= set(PERMISSIONS)
    assert expected <= set(provision_permissions)
