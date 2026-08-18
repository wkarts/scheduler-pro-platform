from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from app.core.config import settings


def local_acme_status() -> dict[str, Any]:
    """Return non-secret diagnostics for the locally managed wildcard certificate."""

    cert_dir = Path(settings.local_acme_cert_dir)
    fullchain = cert_dir / "fullchain.pem"
    private_key = cert_dir / "privkey.pem"
    installed_marker = cert_dir / "last-cloudpanel-installed-at.txt"
    domain = settings.effective_local_acme_domain
    wildcard = f"*.{domain}"

    result: dict[str, Any] = {
        "configured": settings.tls_provisioning_mode == "local_acme",
        "mode": settings.tls_provisioning_mode,
        "domain": domain,
        "wildcard": wildcard,
        "cert_dir": str(cert_dir),
        "certificate_present": fullchain.is_file(),
        "private_key_present": private_key.is_file(),
        "cloudpanel_installed": installed_marker.is_file(),
        "ok": False,
    }
    if installed_marker.is_file():
        try:
            result["cloudpanel_installed_at"] = installed_marker.read_text(
                encoding="utf-8"
            ).strip()
        except OSError:
            pass

    if not fullchain.is_file():
        result["status"] = "MISSING_CERTIFICATE"
        return result

    try:
        pem = fullchain.read_bytes()
        first_certificate = pem.split(b"-----END CERTIFICATE-----", 1)[0]
        first_certificate += b"-----END CERTIFICATE-----\n"
        certificate = x509.load_pem_x509_certificate(first_certificate)
        try:
            san = certificate.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
            dns_names = sorted(set(san.get_values_for_type(x509.DNSName)))
        except x509.ExtensionNotFound:
            dns_names = []

        not_after = getattr(certificate, "not_valid_after_utc", None)
        if not_after is None:
            not_after = certificate.not_valid_after.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        days_remaining = int((not_after - now).total_seconds() // 86400)
        covers_domain = domain in dns_names
        covers_wildcard = wildcard in dns_names
        result.update(
            {
                "dns_names": dns_names,
                "not_after": not_after.isoformat(),
                "days_remaining": days_remaining,
                "covers_domain": covers_domain,
                "covers_wildcard": covers_wildcard,
            }
        )
        result["ok"] = bool(
            private_key.is_file()
            and installed_marker.is_file()
            and covers_domain
            and covers_wildcard
            and days_remaining >= 1
        )
        result["status"] = "READY" if result["ok"] else "INCOMPLETE"
    except (OSError, ValueError) as exc:
        result["status"] = "INVALID_CERTIFICATE"
        result["error"] = exc.__class__.__name__
    return result
