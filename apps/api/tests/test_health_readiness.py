from app.api.v1.routes.health import _tenant_probe_required
from app.core.config import settings


def test_production_readiness_does_not_resolve_internal_probe_as_tenant(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "public_platform_domain", "scheduler.example.com")

    assert _tenant_probe_required("127.0.0.1") is False
    assert _tenant_probe_required("localhost") is False
    assert _tenant_probe_required("::1") is False
    assert _tenant_probe_required("scheduler.example.com") is False
    assert _tenant_probe_required("tenant.scheduler.example.com") is True


def test_development_readiness_keeps_local_tenant_probe(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "public_platform_domain", "localhost")

    assert _tenant_probe_required("localhost") is True
