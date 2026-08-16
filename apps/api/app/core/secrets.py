import base64
import hashlib
import os
from abc import ABC, abstractmethod
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class SecretResolutionError(RuntimeError):
    pass


class SecretResolver(ABC):
    @abstractmethod
    def resolve(self, reference: str) -> str:
        raise NotImplementedError


class EnvSecretResolver(SecretResolver):
    PREFIX = "secret://env/"

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def resolve(self, reference: str) -> str:
        if not reference.startswith(self.PREFIX):
            raise SecretResolutionError("Secret reference must use the secret://env/ scheme.")
        key = reference[len(self.PREFIX):].strip()
        if not key or "/" in key or "\\" in key:
            raise SecretResolutionError("Invalid environment secret reference.")
        value = self._environ.get(key)
        if not value:
            raise SecretResolutionError(f"Environment secret {key} is not configured.")
        return value


class SealedSecretResolver(SecretResolver):
    PREFIX = "secret://sealed/"

    def __init__(self, master_key: str) -> None:
        digest = hashlib.sha256(master_key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def seal(self, value: str) -> str:
        token = self._fernet.encrypt(value.encode("utf-8")).decode("ascii")
        return f"{self.PREFIX}{token}"

    def resolve(self, reference: str) -> str:
        if not reference.startswith(self.PREFIX):
            raise SecretResolutionError("Secret reference must use the secret://sealed/ scheme.")
        token = reference[len(self.PREFIX):].strip()
        if not token:
            raise SecretResolutionError("Invalid sealed secret reference.")
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, UnicodeError) as exc:
            raise SecretResolutionError("Unable to decrypt sealed secret reference.") from exc


class CompositeSecretResolver(SecretResolver):
    def __init__(self, env: EnvSecretResolver, sealed: SealedSecretResolver) -> None:
        self.env = env
        self.sealed = sealed

    def resolve(self, reference: str) -> str:
        if reference.startswith(EnvSecretResolver.PREFIX):
            return self.env.resolve(reference)
        if reference.startswith(SealedSecretResolver.PREFIX):
            return self.sealed.resolve(reference)
        raise SecretResolutionError("Unsupported secret reference scheme.")

    def seal(self, value: str) -> str:
        return self.sealed.seal(value)


sealed_secret_resolver = SealedSecretResolver(settings.app_secret_key)
secret_resolver = CompositeSecretResolver(EnvSecretResolver(), sealed_secret_resolver)


def seal_secret(value: str) -> str:
    return sealed_secret_resolver.seal(value)
