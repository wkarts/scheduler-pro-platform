import pytest

from app.core.errors import APIError
from app.services.cloudflare_service import CloudflareService


@pytest.mark.asyncio
async def test_account_id_configurado_e_substituido_pela_zone_correta(monkeypatch) -> None:
    service = CloudflareService(
        "token",
        "account-id-incorreto",
        custom_hostname_origin="proxy.scheduler.argws.com.br",
    )
    calls: list[str] = []

    async def fake_request(method: str, path: str, *, payload=None):
        calls.append(path)
        if path == "/zones/account-id-incorreto":
            raise APIError("CLOUDFLARE_AUTH_ERROR", "sem acesso", 424)
        if path.startswith("/zones?name=proxy.scheduler.argws.com.br"):
            return {"success": True, "result": []}
        if path.startswith("/zones?name=scheduler.argws.com.br"):
            return {"success": True, "result": []}
        if path.startswith("/zones?name=argws.com.br"):
            return {
                "success": True,
                "result": [{"id": "zone-id-correto", "name": "argws.com.br", "status": "active"}],
            }
        raise AssertionError(f"request inesperada: {method} {path} {payload}")

    monkeypatch.setattr(service, "_request", fake_request)

    zone = await service.resolve_zone()

    assert zone["id"] == "zone-id-correto"
    assert zone["name"] == "argws.com.br"
    assert zone["configured_zone_id"] == "account-id-incorreto"
    assert zone["auto_resolved"] is True
    assert service.zone_id == "zone-id-correto"
    assert any("name=argws.com.br" in path for path in calls)


@pytest.mark.asyncio
async def test_dns_e_purge_usam_zone_resolvida(monkeypatch) -> None:
    service = CloudflareService(
        "token",
        None,
        custom_hostname_origin="proxy.scheduler.argws.com.br",
    )
    calls: list[tuple[str, str, object]] = []

    async def fake_request(method: str, path: str, *, payload=None):
        calls.append((method, path, payload))
        if path.startswith("/zones?name=proxy.scheduler.argws.com.br"):
            return {"success": True, "result": []}
        if path.startswith("/zones?name=scheduler.argws.com.br"):
            return {"success": True, "result": []}
        if path.startswith("/zones?name=argws.com.br"):
            return {
                "success": True,
                "result": [{"id": "zone-id-correto", "name": "argws.com.br", "status": "active"}],
            }
        if path.startswith("/zones/zone-id-correto/dns_records?"):
            return {"success": True, "result": []}
        if path == "/zones/zone-id-correto/purge_cache":
            return {"success": True, "result": {"id": "zone-id-correto"}}
        raise AssertionError(f"request inesperada: {method} {path} {payload}")

    monkeypatch.setattr(service, "_request", fake_request)

    dns = await service.list_dns_records("cliente.scheduler.argws.com.br", "CNAME")
    purge = await service.purge_cache("cliente.scheduler.argws.com.br")

    assert dns["success"] is True
    assert purge["success"] is True
    assert any("/zones/zone-id-correto/dns_records?" in path for _, path, _ in calls)
    assert (
        "POST",
        "/zones/zone-id-correto/purge_cache",
        {"hosts": ["cliente.scheduler.argws.com.br"]},
    ) in calls
