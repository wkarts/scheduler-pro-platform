from app.api.v1.routes.whatsapp import _as_image_data_uri, _qr_payload


def test_qr_payload_reads_direct_evolution_v2_shape() -> None:
    image = "data:image/png;base64," + ("A" * 1024)
    result = _qr_payload(
        {
            "count": 1,
            "pairingCode": "1234-5678",
            "code": "raw-qr-code-value-with-enough-content-to-be-valid",
            "base64": image,
        }
    )

    assert result is not None
    assert result["base64"] == image
    assert result["pairing_code"] == "1234-5678"
    assert result["count"] == 1


def test_qr_payload_finds_nested_connection_shape() -> None:
    raw_base64 = "B" * 1024
    result = _qr_payload(
        {
            "instance": "scheduler-pro-test",
            "ensure": {"created": True},
            "connection": {
                "qrcode": {
                    "base64": raw_base64,
                    "pairingCode": None,
                    "count": 2,
                }
            },
        }
    )

    assert result is not None
    assert result["base64"] == f"data:image/png;base64,{raw_base64}"
    assert result["count"] == 2


def test_short_qr_text_is_not_mistaken_for_image() -> None:
    assert _as_image_data_uri("short-raw-code") is None
