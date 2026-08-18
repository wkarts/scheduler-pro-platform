import socket

from app.core.config import settings
from app.services.local_acme_service import local_acme_status


def test_local_acme_status_reports_unreachable_docker_edge(monkeypatch) -> None:
    monkeypatch.setattr(settings, "tls_provisioning_mode", "local_acme")
    monkeypatch.setattr(settings, "tenant_default_domain_root", "scheduler.argws.com.br")
    monkeypatch.setattr(settings, "local_acme_domain", None)
    monkeypatch.setenv("LOCAL_ACME_PROBE_HOST", "scheduler-edge")
    monkeypatch.setenv("LOCAL_ACME_PROBE_PORT", "443")

    def unavailable(*_args, **_kwargs):
        raise OSError("edge unavailable")

    monkeypatch.setattr(socket, "create_connection", unavailable)

    status = local_acme_status()

    assert status["configured"] is True
    assert status["edge"] == "docker_traefik"
    assert status["domain"] == "scheduler.argws.com.br"
    assert status["wildcard"] == "*.scheduler.argws.com.br"
    assert status["certificate_present"] is False
    assert status["status"] == "EDGE_UNREACHABLE"
    assert status["ok"] is False
