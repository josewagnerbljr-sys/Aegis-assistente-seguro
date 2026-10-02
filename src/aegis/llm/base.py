from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class LLMRequest:
    system: str
    user: str
    max_tokens: int = 600


class ProviderError(Exception):
    """Erro do provedor. Nunca inclui corpo da resposta (pode conter dados sensíveis)."""


class LLMProvider(abc.ABC):
    name: str

    @abc.abstractmethod
    async def generate(self, req: LLMRequest) -> str: ...
