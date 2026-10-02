"""Pipeline de atendimento orquestrado pelo barramento seguro.

req.received -> [guarda de entrada] -> req.guarded -> [NLU] -> req.understood
  -> [recuperação RAG] -> req.retrieved -> [geração] -> req.generated -> [guarda de saída]
  -> res.<instância do gateway>

Cada estágio é independente e só enxerga o que precisa; falhas viram resposta genérica
(sem stack trace) e evento de auditoria.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
import time
import uuid

from .bus import Envelope, MessageBus
from .config import Settings
from .llm.base import LLMRequest
from .llm.router import LLMRouter
from .nlu import analyze
from .prompts import (
    CANNED,
    WARN_PII,
    WARN_SECRET,
    build_system_prompt,
    build_user_prompt,
    extractive_answer,
)
from .rag import KnowledgeBase
from .security import guardrails, pii
from .security.audit import AuditLog

log = logging.getLogger("aegis.pipeline")
CITE = re.compile(r"\[S(\d+)\]")
INCIDENT_CHUNK = "kb-029"


def stage(fn):
    @functools.wraps(fn)
    async def wrapper(self: Pipeline, env: Envelope) -> None:
        try:
            await fn(self, env)
        except Exception:
            log.exception("falha no estágio %s", fn.__name__)
            self.audit.write("stage_error", env.trace_id, env.payload.get("sub", "?"), {"stage": fn.__name__})
            await self._reply(
                env, answer="Ocorreu um erro interno ao processar sua pergunta. Tente novamente.", intent="erro"
            )

    return wrapper


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        bus: MessageBus,
        audit: AuditLog,
        canary: str,
        kb: KnowledgeBase | None = None,
        llm: LLMRouter | None = None,
    ) -> None:
        self.s, self.bus, self.audit, self.canary = settings, bus, audit, canary
        self.kb, self.llm = kb, llm
        self.instance_id = uuid.uuid4().hex[:8]
        self._pending: dict[str, asyncio.Future] = {}

    # --- registro de papéis ---------------------------------------------------------
    def register_gateway(self) -> None:
        self.bus.subscribe(f"res.{self.instance_id}", self._on_response)

    def register_worker(self) -> None:
        self.bus.subscribe("req.received", self.stage_guard)
        self.bus.subscribe("req.guarded", self.stage_nlu)
        self.bus.subscribe("req.understood", self.stage_retrieve)
        self.bus.subscribe("req.retrieved", self.stage_generate)
        self.bus.subscribe("req.generated", self.stage_output)

    # --- gateway --------------------------------------------------------------------
    async def ask(self, question: str, subject: str, role: str) -> dict:
        trace = uuid.uuid4().hex
        fut = asyncio.get_running_loop().create_future()
        self._pending[trace] = fut
        try:
            await self.bus.publish(
                "req.received",
                trace,
                {"question": question, "sub": subject, "role": role,
                 "reply_to": f"res.{self.instance_id}", "t0": time.time()},
            )
            return await asyncio.wait_for(fut, self.s.request_timeout_s)
        finally:
            self._pending.pop(trace, None)

    async def _on_response(self, env: Envelope) -> None:
        fut = self._pending.get(env.trace_id)
        if fut and not fut.done():
            fut.set_result(env.payload["result"])

    async def _reply(self, env: Envelope, *, answer: str, intent: str, confidence: float = 0.0,
                     sources: list | None = None, next_steps: list | None = None,
                     blocked: bool = False, provider: str | None = None) -> None:
        p = env.payload
        result = {
            "trace_id": env.trace_id,
            "answer": answer,
            "intent": intent,
            "confidence": round(confidence, 3),
            "sources": sources or [],
            "next_steps": next_steps or [],
            "warnings": p.get("warnings", []),
            "blocked": blocked,
            "provider": provider,
            "latency_ms": int((time.time() - p.get("t0", time.time())) * 1000),
        }
        await self.bus.publish(p["reply_to"], env.trace_id, {"result": result})

    def _topics_text(self) -> str:
        return ", ".join(f"{c} ({n})" for c, n in self.kb.topics()) if self.kb else ""

    # --- estágios -------------------------------------------------------------------
    @stage
    async def stage_guard(self, env: Envelope) -> None:
        p = dict(env.payload)
        v = guardrails.check_input(p["question"], self.s.max_input_chars)
        if v.blocked:
            self.audit.write("input_blocked", env.trace_id, p["sub"], {"reason": v.reason})
            await self._reply(env, answer=CANNED[v.reason], intent="bloqueado", blocked=True)
            return
        red = pii.redact(v.text)
        p["question"] = red.text
        warnings = []
        if set(red.types) & pii.SECRET_TYPES:
            warnings.append(WARN_SECRET)
        if set(red.types) - pii.SECRET_TYPES:
            warnings.append(WARN_PII)
        p["warnings"] = warnings
        p["redacted"] = red.types
        await self.bus.publish("req.guarded", env.trace_id, p)

    @stage
    async def stage_nlu(self, env: Envelope) -> None:
        p = dict(env.payload)
        r = analyze(p["question"])
        if r.intent in ("saudacao", "agradecimento", "ajuda"):
            await self._reply(env, answer=CANNED[r.intent].format(topicos=self._topics_text()), intent=r.intent)
            return
        p["nlu"] = r.as_dict()
        await self.bus.publish("req.understood", env.trace_id, p)

    @stage
    async def stage_retrieve(self, env: Envelope) -> None:
        p = dict(env.payload)
        hits = self.kb.search(p["question"], topics=p["nlu"]["topics"], k=3)
        if not hits or hits[0].confidence < self.s.min_confidence:
            conf = hits[0].confidence if hits else 0.0
            self.audit.write("no_answer", env.trace_id, p["sub"],
                             {"confidence": round(conf, 3), "q": self.audit.fingerprint(p["question"])})
            await self._reply(env, answer=CANNED["sem_base"].format(topicos=self._topics_text()),
                              intent="fora_de_escopo", confidence=conf)
            return
        chunks = [h.as_dict() for h in hits]
        if p["nlu"]["urgency"] == "alta" and all(c["id"] != INCIDENT_CHUNK for c in chunks):
            extra = self.kb.get(INCIDENT_CHUNK)
            if extra:
                chunks.append({**extra, "score": 0.0, "confidence": 0.0})
        p["chunks"] = chunks
        await self.bus.publish("req.retrieved", env.trace_id, p)

    def _acceptable(self, text: str, n_chunks: int) -> bool:
        cites = [int(x) for x in CITE.findall(text)]
        return (
            bool(cites)
            and all(1 <= c <= n_chunks for c in cites)
            and len(text) <= 4000
            and self.canary not in text
        )

    @stage
    async def stage_generate(self, env: Envelope) -> None:
        p = dict(env.payload)
        chunks = p["chunks"]
        answer, provider = extractive_answer(chunks), "extractive"
        if self.llm and self.llm.has_remote:
            req = LLMRequest(
                system=build_system_prompt(self.canary, p["nlu"]["lang"]),
                user=build_user_prompt(p["question"], chunks),
            )
            text, name = await self.llm.generate(req)
            if text and self._acceptable(text, len(chunks)):
                answer, provider = text.strip(), name
            else:
                self.audit.write("llm_rejected", env.trace_id, p["sub"], {"provider": name})
        p["answer"], p["provider"] = answer, provider
        await self.bus.publish("req.generated", env.trace_id, p)

    @stage
    async def stage_output(self, env: Envelope) -> None:
        p = env.payload
        chunks = p["chunks"]
        answer = p["answer"]
        if self.canary in answer:  # vazamento do prompt: descarta e usa resposta determinística
            self.audit.write("canary_leak", env.trace_id, p["sub"], {})
            answer = extractive_answer(chunks)
        red = pii.redact(answer)  # DLP de saída
        if red.types:
            self.audit.write("output_redacted", env.trace_id, p["sub"], {"types": red.types})
        cited = {int(x) for x in CITE.findall(red.text)} | {1}
        sources = [
            {"id": c["id"], "titulo": c["titulo"], "categoria": c["categoria"], "fontes": c.get("fontes", [])}
            for i, c in enumerate(chunks, 1) if i in cited
        ]
        steps = list(chunks[0]["passos"])[:5]
        if p["nlu"]["urgency"] == "alta":
            inc = next((c for c in chunks if c["id"] == INCIDENT_CHUNK), None)
            if inc:
                steps = list(inc["passos"])[:5]
        self.audit.write("answered", env.trace_id, p["sub"], {
            "intent": p["nlu"]["intent"], "sources": [s["id"] for s in sources],
            "provider": p["provider"], "q": self.audit.fingerprint(p["question"]),
            "redacted": p.get("redacted", []),
        })
        await self._reply(env, answer=red.text, intent=p["nlu"]["intent"],
                          confidence=chunks[0]["confidence"], sources=sources,
                          next_steps=steps, provider=p["provider"])
