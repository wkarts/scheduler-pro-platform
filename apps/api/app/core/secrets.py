import os
from abc import ABC, abstractmethod
from collections.abc import Mapping


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


secret_resolver: SecretResolver = EnvSecretResolver()
