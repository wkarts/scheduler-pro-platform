import pytest

from app.core.secrets import EnvSecretResolver, SecretResolutionError


def test_env_secret_resolver_resolves_reference_without_accepting_literal_password() -> None:
    resolver = EnvSecretResolver({"TENANT_PASSWORD": "correct-secret"})
    assert resolver.resolve("secret://env/TENANT_PASSWORD") == "correct-secret"

    with pytest.raises(SecretResolutionError):
        resolver.resolve("correct-secret")


def test_env_secret_resolver_rejects_missing_variable() -> None:
    resolver = EnvSecretResolver({})
    with pytest.raises(SecretResolutionError):
        resolver.resolve("secret://env/MISSING_SECRET")
