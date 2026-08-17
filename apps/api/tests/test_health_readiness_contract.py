from pathlib import Path

from app.api.v1.routes.health import PLATFORM_MIGRATION_HEAD, _tenant_probe_required


def test_platform_readiness_does_not_resolve_loopback_as_tenant() -> None:
    assert _tenant_probe_required("localhost") is False
    assert _tenant_probe_required("127.0.0.1") is False
    assert _tenant_probe_required("::1") is False


def test_real_development_tenant_hostname_still_requires_tenant_probe() -> None:
    assert _tenant_probe_required("dev.localhost") is True


def test_readiness_tracks_current_platform_migration_head() -> None:
    assert PLATFORM_MIGRATION_HEAD == "platform_0007"


def test_foundation_integration_tracks_same_platform_migration_head() -> None:
    source = Path(__file__).with_name("test_foundation_integration.py").read_text(encoding="utf-8")
    assert f'PLATFORM_MIGRATION_HEAD = "{PLATFORM_MIGRATION_HEAD}"' in source
