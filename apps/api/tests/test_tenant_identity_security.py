import io
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin
from pydantic import ValidationError

from app.core.errors import APIError
from app.tenant_identity.avatar import MAX_UPLOAD, sanitize_avatar
from app.tenant_identity.schemas import GroupInput, ProfileInput, UserCreate, UserUpdate
from app.tenant_identity.service import ensure_delegation


@pytest.mark.parametrize(
    "grants,allowed",
    [
        ({"tenant.manage"}, set()),
        ({"users.manage", "tenant.manage"}, {"users.manage"}),
        ({"groups.manage"}, {"users.read"}),
    ],
)
def test_delegation_cannot_exceed_current_rights(grants, allowed):
    with pytest.raises(APIError):
        ensure_delegation(grants, allowed)


def test_subset_and_empty_grants_are_allowed():
    ensure_delegation(set(), {"users.read"})
    ensure_delegation({"users.read"}, {"users.read", "users.manage"})


@pytest.mark.parametrize(
    "schema,payload",
    [
        (ProfileInput, {"display_name": "Teste", "group_ids": []}),
        (ProfileInput, {"display_name": "Teste", "is_active": True}),
        (UserUpdate, {"display_name": "Teste", "email": "other@example.com"}),
        (UserCreate, {"display_name": "Teste", "email": "one@example.com", "is_super_admin": True}),
        (GroupInput, {"name": "Teste", "permissions": ["users.read"], "is_super_admin": True}),
    ],
)
def test_mass_assignment_is_denied(schema, payload):
    with pytest.raises(ValidationError):
        schema(**payload)


def test_optional_professional_and_no_implicit_groups():
    user = UserCreate(display_name="Sem profissional", email="admin@example.com")
    assert user.professional_id is None and user.group_ids == []


@pytest.mark.parametrize(
    "mime", ["text/html", "image/svg+xml", "application/octet-stream", "image/gif"]
)
def test_avatar_allowlist(mime):
    with pytest.raises(APIError):
        sanitize_avatar(b"<svg/>", mime)


def test_avatar_size_and_content_are_validated():
    for payload in [b"", b"not a png", b"x" * (MAX_UPLOAD + 1)]:
        with pytest.raises(APIError):
            sanitize_avatar(payload, "image/png")


def test_avatar_reencodes_strips_metadata_and_limits_dimensions():
    stream = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("sensitive", "metadata-not-to-persist")
    Image.new("RGB", (800, 600)).save(stream, "PNG", pnginfo=metadata)
    result = sanitize_avatar(stream.getvalue(), "image/png")
    with Image.open(io.BytesIO(result)) as img:
        assert img.size == (512, 384) and img.format == "PNG"
        assert "sensitive" not in img.info


def test_avatar_mime_mismatch_animation_and_pixel_bomb_rejected():
    stream = io.BytesIO()
    Image.new("RGB", (12, 12)).save(stream, "PNG")
    with pytest.raises(APIError):
        sanitize_avatar(stream.getvalue(), "image/jpeg")
    stream = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(
        stream,
        "PNG",
        save_all=True,
        append_images=[Image.new("RGB", (10, 10), "blue")],
        duration=50,
    )
    with pytest.raises(APIError):
        sanitize_avatar(stream.getvalue(), "image/png")
    stream = io.BytesIO()
    Image.new("RGB", (4096, 4096)).save(stream, "PNG")
    with pytest.raises(APIError):
        sanitize_avatar(stream.getvalue(), "image/png")


def test_incremental_migration_preserves_accounts_and_links_optional():
    source = Path("migrations/alembic_tenant/versions/0014_identity.py").read_text()
    assert "tenant_0013_integrations" in source
    assert "verification_required boolean not null default false" in source
    assert "professional_id uuid references professionals(id) on delete set null" in source
    assert "delete from users" not in source and "drop table users" not in source


def test_new_api_scope_is_not_implicitly_delegated_to_machine_tokens():
    from app.integration_services.catalog import scope_for

    assert scope_for("/api/v1/access/profile/password", "POST", False) is None
    assert scope_for("/api/v1/access/users", "POST", False) is None


def test_ui_contract_no_integration_modal_and_free_service():
    root = Path(__file__).resolve().parents[3]
    if not (root / "packages").exists():
        pytest.skip("frontend sources not shipped in API-only image")
    for app in ["web", "admin"]:
        assert "IntegrationServicesLauncher" not in (root / f"apps/{app}/src/main.ts").read_text()
    view = (root / "packages/integration-services/IntegrationServicesView.vue").read_text()
    assert "<dialog" not in view and "<Teleport" not in view
    operator = (root / "apps/web/src/TenantAgendaOperator.vue").read_text()
    assert '<select v-model="selectedServiceId"' not in operator
    assert 'v-model:text="freeService"' in operator and "allow-custom" in operator
