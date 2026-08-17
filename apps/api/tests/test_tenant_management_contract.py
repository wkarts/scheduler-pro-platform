from app.api.v1.routes.tenant_management import (
    TenantPrincipalAdminUpdateRequest,
    TenantUpdateRequest,
)


def test_tenant_update_requires_at_least_one_field() -> None:
    try:
        TenantUpdateRequest()
    except ValueError:
        return
    raise AssertionError("TenantUpdateRequest deveria rejeitar payload vazio")


def test_principal_admin_password_requires_minimum_length() -> None:
    try:
        TenantPrincipalAdminUpdateRequest(password="curta")
    except ValueError:
        return
    raise AssertionError("Senha curta deveria ser rejeitada")


def test_principal_admin_accepts_secure_password() -> None:
    payload = TenantPrincipalAdminUpdateRequest(password="SenhaNova-2026!")
    assert payload.password == "SenhaNova-2026!"
