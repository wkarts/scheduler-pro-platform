from importlib import import_module
from pathlib import Path

from app.api.v1.routes.tenant_management import (
    TenantPrincipalAdminUpdateRequest,
    TenantUpdateRequest,
)
from app.workers.celery_app import celery_app

ROOT = Path(__file__).resolve().parents[1]


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


def test_tenant_resolver_uses_asyncpg_safe_uuid_cast() -> None:
    source = (ROOT / "app/services/tenant_resolver.py").read_text(encoding="utf-8")
    assert ":tenant_id::uuid" not in source
    assert "cast(:tenant_id as uuid)" in source


def test_whatsapp_worker_uses_asyncpg_safe_uuid_cast() -> None:
    source = (ROOT / "app/workers/tasks.py").read_text(encoding="utf-8")
    assert ":id::uuid" not in source
    assert "cast(:id as uuid)" in source


def test_notification_sweep_task_is_registered_by_celery() -> None:
    import_module("app.workers.tasks")
    assert "app.workers.tasks.process_all_due_notifications" in celery_app.tasks
    assert "app.workers.tasks.process_due_notifications" in celery_app.tasks
