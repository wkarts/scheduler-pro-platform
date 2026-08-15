from abc import ABC, abstractmethod

from app.core.config import settings


class WhatsAppProvider(ABC):
    @abstractmethod
    async def connect_instance(self) -> dict[str, object]: ...

    @abstractmethod
    async def connection_status(self) -> dict[str, object]: ...

    @abstractmethod
    async def send_text(self, to: str, message: str) -> dict[str, object]: ...


class EvolutionWhatsAppProvider(WhatsAppProvider):
    async def connect_instance(self) -> dict[str, object]:
        return {"provider": "whatsapp_api", "implementation": "evolution", "qr_code": None, "status": "pending"}

    async def connection_status(self) -> dict[str, object]:
        return {"connected": False, "status": "not_connected"}

    async def send_text(self, to: str, message: str) -> dict[str, object]:
        return {"to": to, "message": message, "queued": True}


class WhatsAppProviderFactory:
    @staticmethod
    def make() -> WhatsAppProvider:
        if settings.whatsapp_provider == "evolution":
            return EvolutionWhatsAppProvider()
        return EvolutionWhatsAppProvider()
