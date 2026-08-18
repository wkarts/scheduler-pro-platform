from pathlib import Path

from app.core.config import settings
from app.services.local_acme_service import local_acme_status


def test_local_acme_status_reports_missing_certificate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "tls_provisioning_mode", "local_acme")
    monkeypatch.setattr(settings, "tenant_default_domain_root", "scheduler.argws.com.br")
    monkeypatch.setattr(settings, "local_acme_domain", None)
    monkeypatch.setattr(settings, "local_acme_cert_dir", str(tmp_path))

    status = local_acme_status()

    assert status["configured"] is True
    assert status["domain"] == "scheduler.argws.com.br"
    assert status["wildcard"] == "*.scheduler.argws.com.br"
    assert status["certificate_present"] is False
    assert status["private_key_present"] is False
    assert status["cloudpanel_installed"] is False
    assert status["status"] == "MISSING_CERTIFICATE"
    assert status["ok"] is False
