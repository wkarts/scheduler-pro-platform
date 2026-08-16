import pytest

from app.core.secrets import EnvSecretResolver, SealedSecretResolver, SecretResolutionError


def test_env_secret_resolver_resolves_reference_without_accepting_literal_password() -> None:
    resolver = EnvSecretResolver({"TENANT_PASSWORD": "correct-secret"})
    assert resolver.resolve("secret://env/TENANT_PASSWORD") == "correct-secret"

    with pytest.raises(SecretResolutionError):
        resolver.resolve("correct-secret")


def test_env_secret_resolver_rejects_missing_variable() -> None:
    resolver = EnvSecretResolver({})
    with pytest.raises(SecretResolutionError):
        resolver.resolve("secret://env/MISSING_SECRET")


def test_sealed_secret_resolver_round_trip() -> None:
    resolver = SealedSecretResolver("master-key-for-test")
    reference = resolver.seal("tenant-password-123")
    assert reference.startswith("secret://sealed/")
    assert "tenant-password-123" not in reference
    assert resolver.resolve(reference) == "tenant-password-123"


def test_sealed_secret_resolver_rejects_tampered_token() -> None:
    resolver = SealedSecretResolver("master-key-for-test")
    reference = resolver.seal("tenant-password-123")
    with pytest.raises(SecretResolutionError):
        resolver.resolve(reference[:-4] + "AAAA")
