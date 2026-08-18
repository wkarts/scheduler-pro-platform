from pathlib import Path

from app.workers.celery_app import celery_app


def test_local_acme_reconciliation_is_routed_to_domains_queue() -> None:
    route = celery_app.conf.task_routes["app.workers.tasks.reconcile_managed_domains"]
    assert route["queue"] == "domains"
    assert route["routing_key"] == "domains"


def test_local_acme_reconciliation_runs_every_ten_minutes() -> None:
    schedule = celery_app.conf.beat_schedule["managed-domain-reconcile-every-ten-minutes"]
    assert schedule["task"] == "app.workers.tasks.reconcile_managed_domains"
    assert "*/10" in str(schedule["schedule"])


def test_reconciliation_uses_configured_dns_proxy_mode() -> None:
    source = Path(__file__).parents[1] / "app" / "workers" / "tasks.py"
    text = source.read_text(encoding="utf-8")
    assert "settings.cloudflare_temporary_record_proxied" in text
    assert "DomainProvisioningService(session).check_domain" not in text
    assert "service.check_domain" in text
