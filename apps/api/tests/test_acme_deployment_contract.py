from pathlib import Path


def test_argws_compose_starts_acme_and_cloudpanel_agent() -> None:
    compose = Path("../../deployments/cloudpanel/compose.argws.yaml").resolve().read_text(
        encoding="utf-8"
    )

    assert "scheduler-acme:" in compose
    assert "scheduler-cloudpanel-agent:" in compose
    assert "CF_Token:" in compose
    assert "ACME_DOMAIN:" in compose
    assert "CLOUDFLARE_MANAGED_WILDCARD_DNS:" in compose
    assert "CLOUDFLARE_MANAGED_WILDCARD_TARGET:" in compose
    assert "privileged: true" in compose
    assert "network_mode: none" in compose
    assert "- /:/host:rw" in compose
    assert "cloudpanel-agent:${APP_IMAGE_TAG:-latest}" in compose
    assert "acme:${APP_IMAGE_TAG:-latest}" in compose
    assert "./scripts/acme-dns01-cloudflare.sh" not in compose


def test_cloudpanel_vhost_example_is_single_wildcard_server_name() -> None:
    vhost = Path("../../deployments/cloudpanel/VHOST_WILDCARD_EXAMPLE.conf").resolve().read_text(
        encoding="utf-8"
    )

    assert "server_name scheduler.argws.com.br *.scheduler.argws.com.br;" in vhost
    assert vhost.count("server {") == 1


def test_embedded_acme_entrypoint_uses_dns01_and_wildcard() -> None:
    script = Path("../../infrastructure/docker/acme/entrypoint.sh").resolve().read_text(
        encoding="utf-8"
    )

    assert "--dns dns_cf" in script
    assert '-d "*.$DOMAIN"' in script
    assert "--force" not in script
    assert "_acme-challenge" in script
    assert "acme.sh --cron" in script


def test_cloudpanel_agent_reconciles_vhost_and_certificate_without_network() -> None:
    script = Path(
        "../../infrastructure/docker/cloudpanel-agent/entrypoint.sh"
    ).resolve().read_text(encoding="utf-8")

    assert "clpctl site:install:certificate" in script
    assert "nginx -t" in script
    assert "WILDCARD_DOMAIN" in script
    assert "last-cloudpanel-installed-at.txt" in script
    assert "Reverse Proxy/VHost" in script
