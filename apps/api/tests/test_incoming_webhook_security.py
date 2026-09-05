"""Schema and cryptographic regressions, without network calls or live secrets."""

import json
import time

import pytest
from fastapi import Request
from pydantic import ValidationError

from app.core.errors import APIError
from app.integration_services.catalog import scope_for
from app.integration_services.incoming import ReceiverInput, parse_event, verify_signature
from app.integration_services.routes import TokenInput, TokenValidityInput
from app.integration_services.webhooks import signature


def test_api_expiration_is_optional_and_explicitly_clearable():
    base = {"name": "ERP access", "scopes": ["customers.read"]}
    assert TokenInput(**base).expires_in_days is None
    assert TokenInput(**base, expires_in_days=None).expires_in_days is None
    assert TokenInput(**base, expires_in_days=30).expires_in_days == 30
    assert TokenValidityInput(expires_in_days=None).expires_in_days is None
    with pytest.raises(ValidationError):
        TokenValidityInput()


@pytest.mark.parametrize("days", [0, -1, 366, "", "30", True, 1.5])
def test_bad_validity_is_not_silently_converted_to_indefinite(days):
    with pytest.raises(ValidationError):
        TokenInput(name="ERP access", scopes=["customers.read"], expires_in_days=days)


def test_canonical_fingerprint_ignores_key_order_not_event_contents():
    first = parse_event(b'{"id":"a","type":"event.created","data":{"value":1}}')
    second = parse_event(b'{ "data": {"value": 1}, "type": "event.created", "id": "a" }')
    assert first[2] == second[2]
    assert first[2] != parse_event(b'{"id":"a","type":"event.created","data":{"value":2}}')[2]


@pytest.mark.parametrize(
    "raw",
    [
        b"[]",
        b"{}",
        b'{"id":"a","id":"b","type":"x","data":{}}',
        b'{"id":"a","type":"x","data":{"v":NaN}}',
        b'{"id":"a","type":"x","data":[]}',
        b'{"id":1,"type":"x","data":{}}',
        b'{"id":"a","type":"x","data":{"v":1e999}}',
        b"\xff",
    ],
)
def test_rejects_ambiguous_or_invalid_envelopes(raw):
    with pytest.raises(APIError) as exc:
        parse_event(raw)
    assert exc.value.status_code == 422


def request_headers(timestamp, delivery, supplied):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/hooks/tenant/a",
            "headers": [
                (b"x-scheduler-timestamp", str(timestamp).encode()),
                (b"x-scheduler-delivery-id", delivery.encode()),
                (b"x-scheduler-signature", supplied.encode()),
            ],
        }
    )


def test_hmac_binds_raw_body_delivery_id_and_attempt_time():
    raw = json.dumps(
        {"id": "unique-id", "type": "x", "data": {"name": "ação"}}, ensure_ascii=False
    ).encode()
    stamp = str(int(time.time()))
    signed = signature("secret-test-only", stamp, "delivery-1", raw)
    request = request_headers(stamp, "delivery-1", signed)
    verify_signature("secret-test-only", request, raw)
    for secret, body, headers in [
        ("wrong", raw, request),
        ("secret-test-only", raw + b" ", request),
        ("secret-test-only", raw, request_headers(stamp, "different", signed)),
        ("secret-test-only", raw, request_headers("garbage", "delivery-1", signed)),
    ]:
        with pytest.raises(APIError):
            verify_signature(secret, headers, body)


@pytest.mark.parametrize("offset", [-400, 400])
def test_hmac_rejects_old_and_future_attempts(offset):
    raw = b"{}"
    stamp = str(int(time.time()) + offset)
    with pytest.raises(APIError):
        verify_signature("s", request_headers(stamp, "id", signature("s", stamp, "id", raw)), raw)


def test_receivers_are_independent_from_machine_credential_issuance():
    for platform, prefix in [(False, "/api/v1"), (True, "/api/v1/platform")]:
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            assert (
                scope_for(
                    prefix + "/integrations/services/receivers/id/rotate-secret", method, platform
                )
                is None
            )
        assert scope_for(prefix + "/integrations/services/receivers", "GET", platform) is not None
    assert scope_for("/api/v1/hooks/tenant/id", "POST", False) is None
    assert ReceiverInput(name="ERP").auth_mode == "hmac"
    with pytest.raises(ValidationError):
        ReceiverInput(name="ERP", auth_mode="none")
    with pytest.raises(ValidationError):
        ReceiverInput(name="ERP", events=["contains spaces"])
