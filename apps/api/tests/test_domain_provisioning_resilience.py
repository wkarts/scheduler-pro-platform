from types import SimpleNamespace

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
