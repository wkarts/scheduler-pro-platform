from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.core.errors import APIError
from app.services.domain_provisioning_service import DomainProvisioningService


def _error() -> APIError:
    return APIError(
        "CLOUDFLARE_AUTH_ERROR",
        "A Cloudflare rejeitou a credencial enviada.",
        424,
        {"status_code": 401},
    )


def test_remote_check_failure_preserves_last_known_active_domain() -> None:
    domain = SimpleNamespace(
        status="ACTIVE",
        validation={"mode": "temporary_dns", "record_exists": True},
    )

    preserved = DomainProvisioningService._preserve_last_known_domain_state(
        domain,
        mode="temporary_dns",
        error_key="last_check_error",
        error=_error(),
        record_exists=False,
    )

    assert preserved is True
    assert domain.status == "ACTIVE"
    assert domain.validation["record_exists"] is True
    assert domain.validation["integration_status"] == "DEGRADED"
    assert domain.validation["last_check_error"]["code"] == "CLOUDFLARE_AUTH_ERROR"


def test_retry_recovers_legacy_pending_domain_when_dns_was_already_verified() -> None:
    domain = SimpleNamespace(
        status="PENDING_VALIDATION",
        validation={"mode": "temporary_dns", "record_exists": True},
    )

    preserved = DomainProvisioningService._preserve_last_known_domain_state(
        domain,
        mode="temporary_dns",
        error_key="last_check_error",
        error=_error(),
        record_exists=False,
    )

    assert preserved is True
    assert domain.status == "ACTIVE"
    assert domain.validation["record_exists"] is True
    assert domain.validation["integration_status"] == "DEGRADED"


def test_remote_failure_keeps_unverified_domain_pending() -> None:
    domain = SimpleNamespace(status="CONFIGURING", validation={})

    preserved = DomainProvisioningService._preserve_last_known_domain_state(
        domain,
        mode="temporary_dns",
        error_key="cloudflare_error",
        error=_error(),
        record_exists=False,
    )

    assert preserved is False
    assert domain.status == "PENDING_VALIDATION"
    assert domain.validation["record_exists"] is False
    assert domain.validation["integration_status"] == "UNVERIFIED"


def test_scheduler_subdomain_is_managed_and_never_requires_cloudflare_saas(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tenant_default_domain_root", "scheduler.argws.com.br")

    assert DomainProvisioningService._is_managed_hostname(
        "wwsoftwares-48ec0e67.scheduler.argws.com.br"
    ) is True
    assert DomainProvisioningService._is_managed_hostname(
        "agenda.cliente.com.br"
    ) is False


def test_local_acme_metadata_uses_wildcard_and_dns_only(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tenant_default_domain_root", "scheduler.argws.com.br")
    monkeypatch.setattr(settings, "local_acme_domain", None)
    monkeypatch.setattr(settings, "tls_provisioning_mode", "local_acme")
    monkeypatch.setattr(settings, "cloudflare_temporary_record_proxied", False)

    metadata = DomainProvisioningService._managed_tls_metadata()

    assert metadata["mode"] == "local_acme"
    assert metadata["wildcard"] == "*.scheduler.argws.com.br"
    assert metadata["dns_proxied"] is False
    assert metadata["issuer"] == "letsencrypt"


@pytest.mark.asyncio
async def test_connect_managed_hostname_reconciles_dns_without_custom_hostname_api(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tenant_default_domain_root", "scheduler.argws.com.br")
    monkeypatch.setattr(settings, "tls_provisioning_mode", "local_acme")
    monkeypatch.setattr(settings, "cloudflare_temporary_record_proxied", False)

    class FakeSession:
        async def commit(self) -> None:
            return None

    service = DomainProvisioningService(FakeSession())  # type: ignore[arg-type]
    domain = SimpleNamespace(
        id="domain-1",
        tenant_id="tenant-1",
        hostname="wwsoftwares-48ec0e67.scheduler.argws.com.br",
        is_primary=True,
        is_temporary=True,
        status="ACTIVE",
        validation={},
    )

    async def fake_tenant(_tenant_id: str) -> SimpleNamespace:
        return SimpleNamespace(id="tenant-1")

    async def fake_domain(_hostname: str) -> SimpleNamespace:
        return domain

    dns_calls: list[dict[str, object]] = []

    async def fake_dns_record(
        hostname: str,
        target: str,
        *,
        record_type: str,
        proxied: bool,
    ) -> dict[str, object]:
        dns_calls.append(
            {
                "hostname": hostname,
                "target": target,
                "record_type": record_type,
                "proxied": proxied,
            }
        )
        return {"success": True, "record": {"proxied": proxied}}

    async def forbidden_custom_hostname(_hostname: str) -> dict[str, object]:
        raise AssertionError("Cloudflare Custom Hostnames não deve ser chamado")

    monkeypatch.setattr(service, "_tenant", fake_tenant)
    monkeypatch.setattr(service, "_domain_by_hostname", fake_domain)
    monkeypatch.setattr(service.cloudflare, "ensure_dns_record", fake_dns_record)
    monkeypatch.setattr(service.cloudflare, "ensure_custom_hostname", forbidden_custom_hostname)

    result = await service.connect_custom_domain(
        "tenant-1",
        "wwsoftwares-48ec0e67.scheduler.argws.com.br",
        make_primary=False,
    )

    assert result["status"] == "ACTIVE"
    assert result["validation"]["tls"]["mode"] == "local_acme"
    assert dns_calls == [
        {
            "hostname": "wwsoftwares-48ec0e67.scheduler.argws.com.br",
            "target": settings.tenant_domain_target,
            "record_type": settings.cloudflare_temporary_record_type,
            "proxied": False,
        }
    ]
