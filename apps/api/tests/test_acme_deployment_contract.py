from pathlib import Path


def test_argws_compose_starts_acme_and_exposes_wildcard_settings() -> None:
    compose = Path("../../deployments/cloudpanel/compose.argws.yaml").resolve().read_text(
        encoding="utf-8"
    )

    assert "scheduler-acme:" in compose
    assert "CF_Token:" in compose
    assert "ACME_DOMAIN:" in compose
    assert "CLOUDFLARE_MANAGED_WILDCARD_DNS:" in compose
    assert "CLOUDFLARE_MANAGED_WILDCARD_TARGET:" in compose


def test_cloudpanel_vhost_example_is_single_wildcard_server_name() -> None:
    vhost = Path("../../deployments/cloudpanel/VHOST_WILDCARD_EXAMPLE.conf").resolve().read_text(
        encoding="utf-8"
    )

    assert "server_name scheduler.argws.com.br *.scheduler.argws.com.br;" in vhost
    assert vhost.count("server {") == 1


def test_acme_script_uses_dns01_and_wildcard() -> None:
    script = Path(
        "../../deployments/cloudpanel/scripts/acme-dns01-cloudflare.sh"
    ).resolve().read_text(encoding="utf-8")

    assert "--dns dns_cf" in script
    assert '-d "*.$DOMAIN"' in script
    assert "--force" not in script
    assert "_acme-challenge" in script
