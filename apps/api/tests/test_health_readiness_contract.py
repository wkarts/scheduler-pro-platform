from pathlib import Path

from app.api.v1.routes.health import PLATFORM_MIGRATION_HEAD, _tenant_probe_required
from app.core.config import settings


def test_production_platform_and_loopback_do_not_require_tenant_probe(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "public_platform_domain", "scheduler.example.com")

    assert _tenant_probe_required("localhost") is False
    assert _tenant_probe_required("127.0.0.1") is False
    assert _tenant_probe_required("::1") is False
    assert _tenant_probe_required("scheduler.example.com") is False
    assert _tenant_probe_required("tenant.scheduler.example.com") is True


def test_development_seeded_local_domains_require_tenant_probe(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "public_platform_domain", "localhost")

    assert _tenant_probe_required("localhost") is True
    assert _tenant_probe_required("127.0.0.1") is True
    assert _tenant_probe_required("dev.localhost") is True


def test_readiness_tracks_current_platform_migration_head() -> None:
    assert PLATFORM_MIGRATION_HEAD == "platform_0012_login_surface"


def test_foundation_integration_tracks_same_platform_migration_head() -> None:
    source = Path(__file__).with_name("test_foundation_integration.py").read_text(
        encoding="utf-8"
    )
    assert f'PLATFORM_MIGRATION_HEAD = "{PLATFORM_MIGRATION_HEAD}"' in source
