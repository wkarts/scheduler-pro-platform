from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShortLinkResult:
    original_url: str
    url: str
    provider: str
    shortened: bool
    metadata: dict[str, Any]


class LinkShortener:
    """Provider-neutral short-link engine.

    O fluxo principal nunca depende de serviço externo. Nesta primeira versão o
    provider `none` devolve a URL canônica. Providers pagos/limitados (Bitly,
    Short.io, goo.su etc.) podem ser adicionados depois sem alterar o motor de
    confirmação de agendamento.
    """

    SUPPORTED_PROVIDERS = {"none"}

    async def shorten(
        self,
        url: str,
        *,
        enabled: bool = False,
        provider: str = "none",
        config: dict[str, Any] | None = None,
    ) -> ShortLinkResult:
        clean_provider = (provider or "none").strip().lower()
        if not enabled or clean_provider == "none":
            return ShortLinkResult(
                original_url=url,
                url=url,
                provider="none",
                shortened=False,
                metadata={"reason": "shortener_disabled"},
            )

        # Fail-open é deliberado: uma indisponibilidade/custo de encurtador nunca
        # pode impedir a confirmação do atendimento. Quando providers externos
        # forem implementados, qualquer falha deve retornar a URL canônica.
        return ShortLinkResult(
            original_url=url,
            url=url,
            provider=clean_provider,
            shortened=False,
            metadata={
                "reason": "provider_not_implemented",
                "configured_provider": clean_provider,
                "config_present": bool(config),
            },
        )


link_shortener = LinkShortener()
