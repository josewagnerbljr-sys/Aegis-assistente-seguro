"""Montagem (composition root) dos componentes conforme o papel do processo."""

from __future__ import annotations

from dataclasses import dataclass

from .bus import InMemoryBus, MessageBus, RedisStreamsBus, SecureCodec
from .config import Settings
from .llm.router import LLMRouter
from .pipeline import Pipeline
from .rag import KnowledgeBase
from .security.audit import AuditLog
from .security.auth import AuthService
from .security.crypto import KeyRing
from .security.ratelimit import RateLimiter


@dataclass
class Runtime:
    settings: Settings
    bus: MessageBus
    pipeline: Pipeline
    audit: AuditLog
    auth: AuthService
    limiter: RateLimiter
    login_limiter: RateLimiter


def build_runtime(s: Settings) -> Runtime:
    keys = KeyRing.from_master(s.master_key)
    codec = SecureCodec(keys.bus_enc, keys.bus_mac, s.bus_max_age_s)
    bus: MessageBus = RedisStreamsBus(codec, s.redis_url) if s.bus_backend == "redis" else InMemoryBus(codec)
    audit = AuditLog(s.audit_dir / f"audit-{s.role}.jsonl", keys.audit)
    kb = llm = None
    if s.role in ("worker", "all"):  # privilégio mínimo: o gateway nunca carrega a base
        kb = KnowledgeBase.load(s.kb_path, keys.kb)
        llm = LLMRouter.from_names(s.llm_chain, s.llm_timeout_s)
    pipe = Pipeline(s, bus, audit, keys.canary, kb, llm)
    if s.role in ("api", "all"):
        pipe.register_gateway()
    if s.role in ("worker", "all"):
        pipe.register_worker()
    auth = AuthService(s.users, keys.jwt, s.jwt_issuer, s.jwt_audience, s.jwt_ttl_seconds)
    return Runtime(s, bus, pipe, audit, auth, RateLimiter(s.rate_limit_per_min), RateLimiter(s.login_limit_per_min))
