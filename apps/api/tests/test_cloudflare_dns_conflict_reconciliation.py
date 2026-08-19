import pytest

from app.services.cloudflare_service import CloudflareService


@pytest.mark.asyncio
async def test_ensure_cname_replaces_legacy_a_record(monkeypatch) -> None:
    service = CloudflareService("token", "zone-id")
    records: list[dict[str, object]] = [
        {
            "id": "legacy-a",
            "type": "A",
            "name": "*.scheduler.argws.com.br",
            "content": "217.76.59.202",
            "proxied": False,
            "ttl": 1,
        }
    ]

    async def list_records(
        hostname: str,
        record_type: str | None = None,
    ) -> dict[str, object]:
        visible = [
            dict(item)
            for item in records
            if item["name"] == hostname
            and (record_type is None or item["type"] == record_type.upper())
        ]
        return {"success": True, "result": visible}

    async def delete_record(record_id: str) -> dict[str, object]:
        records[:] = [item for item in records if item["id"] != record_id]
        return {"success": True}

    async def create_record(
        hostname: str,
        target: str,
        *,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict[str, object]:
        records.append(
            {
                "id": "managed-cname",
                "type": record_type,
                "name": hostname,
                "content": target,
                "proxied": proxied,
                "ttl": ttl,
            }
        )
        return {"success": True, "result": dict(records[-1])}

    monkeypatch.setattr(service, "list_dns_records", list_records)
    monkeypatch.setattr(service, "delete_dns_record", delete_record)
    monkeypatch.setattr(service, "create_dns_record", create_record)

    result = await service.ensure_dns_record(
        "*.scheduler.argws.com.br",
        "proxy.scheduler.argws.com.br",
        record_type="CNAME",
        proxied=False,
    )

    assert result["success"] is True
    assert result["result"]["type"] == "CNAME"
    assert result["result"]["content"] == "proxy.scheduler.argws.com.br"
    assert result["removed_conflicts"] == [
        {
            "id": "legacy-a",
            "type": "A",
            "name": "*.scheduler.argws.com.br",
            "content": "217.76.59.202",
            "proxied": False,
        }
    ]
    assert [item["type"] for item in records] == ["CNAME"]


@pytest.mark.asyncio
async def test_ensure_dns_preserves_txt_records(monkeypatch) -> None:
    service = CloudflareService("token", "zone-id")
    records: list[dict[str, object]] = [
        {
            "id": "txt-1",
            "type": "TXT",
            "name": "*.scheduler.argws.com.br",
            "content": "verification-value",
            "proxied": False,
            "ttl": 1,
        }
    ]

    async def list_records(
        hostname: str,
        record_type: str | None = None,
    ) -> dict[str, object]:
        return {
            "success": True,
            "result": [
                dict(item)
                for item in records
                if item["name"] == hostname
                and (record_type is None or item["type"] == record_type.upper())
            ],
        }

    async def delete_record(record_id: str) -> dict[str, object]:
        raise AssertionError(f"TXT não deve ser removido: {record_id}")

    async def create_record(
        hostname: str,
        target: str,
        *,
        record_type: str = "CNAME",
        proxied: bool = True,
        ttl: int = 1,
    ) -> dict[str, object]:
        records.append(
            {
                "id": "cname-1",
                "type": record_type,
                "name": hostname,
                "content": target,
                "proxied": proxied,
                "ttl": ttl,
            }
        )
        return {"success": True}

    monkeypatch.setattr(service, "list_dns_records", list_records)
    monkeypatch.setattr(service, "delete_dns_record", delete_record)
    monkeypatch.setattr(service, "create_dns_record", create_record)

    result = await service.ensure_dns_record(
        "*.scheduler.argws.com.br",
        "proxy.scheduler.argws.com.br",
        proxied=False,
    )

    assert result["success"] is True
    assert result["removed_conflicts"] == []
    assert {str(item["type"]) for item in records} == {"TXT", "CNAME"}
