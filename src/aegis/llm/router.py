"""Barramento de IA generativa: roteia entre provedores com timeout e circuit breaker.

Se todos falharem (ou nenhum estiver configurado), o pipeline usa a resposta extrativa
determinística — o assistente nunca fica indisponível por causa do LLM.
"""

from __future__ import annotations

import asyncio
import logging
import time

from .base import LLMProvider, LLMRequest, ProviderError
from .providers import build_provider

log = logging.getLogger("aegis.llm")


class LLMRouter:
    def __init__(
        self, providers: list[LLMProvider], timeout: float = 20.0, fail_threshold: int = 3, cooldown: float = 30.0
    ) -> None:
        self.providers, self.timeout = providers, timeout
        self.fail_threshold, self.cooldown = fail_threshold, cooldown
        self._fails: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    @property
    def has_remote(self) -> bool:
        return bool(self.providers)

    @classmethod
    def from_names(cls, names: tuple[str, ...], timeout: float) -> LLMRouter:
        providers: list[LLMProvider] = []
        for n in names:
            try:
                providers.append(build_provider(n, timeout))
            except ProviderError as exc:
                log.warning("provedor %s ignorado: %s", n, exc)
        return cls(providers, timeout)

    async def generate(self, req: LLMRequest) -> tuple[str | None, str | None]:
        for p in self.providers:
            if self._open_until.get(p.name, 0) > time.monotonic():
                continue  # circuito aberto
            try:
                text = await asyncio.wait_for(p.generate(req), self.timeout)
                if text and text.strip():
                    self._fails[p.name] = 0
                    return text, p.name
                raise ProviderError("resposta vazia")
            except Exception as exc:  # noqa: BLE001
                n = self._fails.get(p.name, 0) + 1
                self._fails[p.name] = n
                log.warning("provedor %s falhou (%s)", p.name, type(exc).__name__)
                if n >= self.fail_threshold:
                    self._open_until[p.name] = time.monotonic() + self.cooldown
                    self._fails[p.name] = 0
        return None, None
