from types import SimpleNamespace

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
