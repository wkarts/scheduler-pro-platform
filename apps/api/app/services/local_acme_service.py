import os
import socket
import ssl
from datetime import UTC, datetime
from typing import Any, cast

from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from app.core.config import settings


def local_acme_status() -> dict[str, Any]:
    """Return non-secret diagnostics for the Docker-managed wildcard TLS edge.

    O certificado e a chave privada pertencem ao Traefik. A API não monta nem lê
    o acme.json: ela apenas abre uma conexão TLS interna contra o edge Docker e
    inspeciona o certificado público apresentado com SNI do domínio da plataforma.
    """

    domain = settings.effective_local_acme_domain
    wildcard = f"*.{domain}"
    probe_host = os.getenv("LOCAL_ACME_PROBE_HOST", "scheduler-edge").strip() or "scheduler-edge"
    try:
        probe_port = int(os.getenv("LOCAL_ACME_PROBE_PORT", "443"))
    except ValueError:
        probe_port = 443

    result: dict[str, Any] = {
        "configured": settings.tls_provisioning_mode == "local_acme",
        "mode": settings.tls_provisioning_mode,
        "edge": "docker_traefik",
        "domain": domain,
        "wildcard": wildcard,
        "probe_host": probe_host,
        "probe_port": probe_port,
        "certificate_present": False,
        "ok": False,
    }

    try:
        context = ssl.create_default_context()
        with socket.create_connection((probe_host, probe_port), timeout=3) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=domain) as tls_socket:
                der_certificate = tls_socket.getpeercert(binary_form=True)
        if not der_certificate:
            result["status"] = "MISSING_CERTIFICATE"
            return result

        certificate = x509.load_der_x509_certificate(der_certificate)
        try:
            extension = certificate.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            san = cast(x509.SubjectAlternativeName, extension.value)
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
                "certificate_present": True,
                "dns_names": dns_names,
                "not_after": not_after.isoformat(),
                "days_remaining": days_remaining,
                "covers_domain": covers_domain,
                "covers_wildcard": covers_wildcard,
            }
        )
        result["ok"] = bool(covers_domain and covers_wildcard and days_remaining >= 1)
        result["status"] = "READY" if result["ok"] else "INCOMPLETE"
    except (OSError, ssl.SSLError, ValueError) as exc:
        result["status"] = "EDGE_UNREACHABLE"
        result["error"] = exc.__class__.__name__
    return result
