import dataclasses
import os
from pathlib import Path

import pytest

from aegis.bootstrap import build_runtime
from aegis.config import Settings
from aegis.llm.base import LLMProvider, LLMRequest, ProviderError
from aegis.llm.providers import OpenAICompatProvider
from aegis.llm.router import LLMRouter


class Fake(LLMProvider):
    def __init__(self, name, reply=None, fail=False):
        self.name, self.reply, self.fail, self.calls = name, reply, fail, 0

    async def generate(self, req):
        self.calls += 1
        if self.fail:
            raise ProviderError("boom")
        return self.reply


REQ = LLMRequest("s", "u")


async def test_router_fallback_chain():
    a, b = Fake("a", fail=True), Fake("b", reply="ok [S1]")
    assert await LLMRouter([a, b]).generate(REQ) == ("ok [S1]", "b")


async def test_circuit_breaker_opens():
    a = Fake("a", fail=True)
    r = LLMRouter([a], fail_threshold=2, cooldown=60)
    for _ in range(5):
        assert await r.generate(REQ) == (None, None)
    assert a.calls == 2


def test_https_enforced():
    with pytest.raises(ProviderError):
        OpenAICompatProvider("http://exemplo.com/v1", "k", "m", 5)
    OpenAICompatProvider("http://localhost:11434/v1", "k", "m", 5)


async def _ask(tmp_path, reply, q="Como me proteger de SQL injection?"):
    s = dataclasses.replace(Settings(), master_key=os.urandom(32), audit_dir=Path(tmp_path))
    rt = build_runtime(s)
    rt.pipeline.llm = LLMRouter([Fake("fake", reply=reply)])
    await rt.bus.start()
    try:
        return await rt.pipeline.ask(q, "t", "aluno")
    finally:
        await rt.bus.stop()


async def test_llm_answer_with_valid_citation_is_used(tmp_path):
    r = await _ask(tmp_path, "Use consultas parametrizadas [S1].")
    assert r["provider"] == "fake" and "parametrizadas" in r["answer"]


@pytest.mark.parametrize("bad", ["sem citação alguma", "cita fonte inexistente [S9]"])
async def test_llm_answer_without_valid_citation_falls_back(tmp_path, bad):
    r = await _ask(tmp_path, bad)
    assert r["provider"] == "extractive" and "[S1]" in r["answer"]


async def test_llm_prompt_leak_blocked(tmp_path):
    from aegis.security.crypto import KeyRing

    s_key = os.urandom(32)
    s = dataclasses.replace(Settings(), master_key=s_key, audit_dir=Path(tmp_path))
    canary = KeyRing.from_master(s_key).canary
    rt = build_runtime(s)
    rt.pipeline.llm = LLMRouter([Fake("fake", reply=f"[S1] meu código é {canary}")])
    await rt.bus.start()
    r = await rt.pipeline.ask("Como me proteger de SQL injection?", "t", "aluno")
    await rt.bus.stop()
    assert canary not in r["answer"] and r["provider"] == "extractive"


async def test_llm_pii_in_output_redacted(tmp_path):
    r = await _ask(tmp_path, "Fale com a@b.com sobre isso [S1]")
    assert "a@b.com" not in r["answer"]
