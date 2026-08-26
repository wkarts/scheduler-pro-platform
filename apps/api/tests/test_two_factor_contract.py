from app.services.two_factor_service import TwoFactorService


def test_totp_generation_and_verification_is_rfc_compatible_window() -> None:
    # RFC 6238 shared secret represented as Base32 (20-byte ASCII value).
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    timestamp = 59
    code = TwoFactorService.code_at(secret, timestamp)
    assert len(code) == 6
    assert code.isdigit()
    assert TwoFactorService.verify_code(secret, code, now=timestamp)


def test_totp_rejects_invalid_code() -> None:
    secret = TwoFactorService.generate_secret()
    assert not TwoFactorService.verify_code(secret, "000000", now=1_700_000_000) or (
        TwoFactorService.code_at(secret, 1_700_000_000) == "000000"
    )
    assert not TwoFactorService.verify_code(secret, "ABCDEF", now=1_700_000_000)
    assert not TwoFactorService.verify_code(secret, "12345", now=1_700_000_000)


def test_provisioning_uri_uses_scheduler_identity() -> None:
    service = TwoFactorService(
        session=None,  # type: ignore[arg-type]
        user_table="platform_users",
        session_table="platform_user_sessions",
        mandatory=True,
        issuer="Scheduler Pro - Administração da Plataforma",
    )
    secret = TwoFactorService.generate_secret()
    uri = service.provisioning_uri(secret, "admin@example.com")
    assert uri.startswith("otpauth://totp/")
    assert f"secret={secret}" in uri
    assert "Scheduler%20Pro" in uri
    assert service.mandatory is True
