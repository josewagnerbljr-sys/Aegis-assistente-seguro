"""Provedores de IA generativa remotos (HTTPS obrigatório; chaves só via ambiente)."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from .base import LLMProvider, LLMRequest, ProviderError


def _check_url(url: str) -> str:
    p = urlparse(url)
    local = p.hostname in {"localhost", "127.0.0.1", "::1"}
    if p.scheme != "https" and not (p.scheme == "http" and local):
        raise ProviderError("URL do provedor deve ser https (http só para localhost)")
    return url.rstrip("/")


class OpenAICompatProvider(LLMProvider):
    """Qualquer endpoint compatível com /chat/completions (OpenAI, Azure, vLLM, Ollama...)."""

    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float) -> None:
        self.base_url, self._key = _check_url(base_url), api_key
        self.model, self.timeout = model, timeout

    async def generate(self, req: LLMRequest) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self.model,
                    "temperature": 0.1,
                    "max_tokens": req.max_tokens,
                    "messages": [
                        {"role": "system", "content": req.system},
                        {"role": "user", "content": req.user},
                    ],
                },
            )
        if r.status_code != 200:
            raise ProviderError(f"HTTP {r.status_code}")
        try:
            return r.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError("resposta inesperada") from exc


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float) -> None:
        self._key, self.model, self.timeout = api_key, model, timeout
        self.url = "https://api.anthropic.com/v1/messages"

    async def generate(self, req: LLMRequest) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(
                self.url,
                headers={"x-api-key": self._key, "anthropic-version": "2023-06-01"},
                json={
                    "model": self.model,
                    "max_tokens": req.max_tokens,
                    "temperature": 0.1,
                    "system": req.system,
                    "messages": [{"role": "user", "content": req.user}],
                },
            )
        if r.status_code != 200:
            raise ProviderError(f"HTTP {r.status_code}")
        try:
            return "".join(b["text"] for b in r.json()["content"] if b.get("type") == "text")
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("resposta inesperada") from exc


def build_provider(name: str, timeout: float) -> LLMProvider:
    if name == "anthropic":
        key = os.getenv("AEGIS_ANTHROPIC_API_KEY")
        if not key:
            raise ProviderError("AEGIS_ANTHROPIC_API_KEY ausente")
        return AnthropicProvider(key, os.getenv("AEGIS_ANTHROPIC_MODEL", "claude-sonnet-5-5"), timeout)
    if name == "openai_compat":
        key, url = os.getenv("AEGIS_OPENAI_API_KEY"), os.getenv("AEGIS_OPENAI_BASE_URL")
        if not (key and url):
            raise ProviderError("AEGIS_OPENAI_API_KEY e AEGIS_OPENAI_BASE_URL são obrigatórios")
        return OpenAICompatProvider(url, key, os.getenv("AEGIS_OPENAI_MODEL", "gpt-4o-mini"), timeout)
    raise ProviderError(f"provedor desconhecido: {name}")
