"""Configuração centralizada. Nenhum segredo é hard-coded: tudo vem do ambiente."""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("aegis.config")
ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Configuração inválida ou insegura (falha cedo, fail-fast)."""


@dataclass(frozen=True)
class Settings:
    env: str = "dev"  # dev | prod
    role: str = "all"  # api | worker | all
    master_key: bytes = b""
    jwt_ttl_seconds: int = 900
    jwt_issuer: str = "aegis"
    jwt_audience: str = "aegis-api"
    kb_path: Path = ROOT / "data" / "kb" / "base_conhecimento.json"
    audit_dir: Path = ROOT / "var" / "audit"
    bus_backend: str = "memory"  # memory | redis
    redis_url: str = ""
    llm_chain: tuple[str, ...] = ()  # provedores remotos, em ordem de preferência
    max_input_chars: int = 2000
    rate_limit_per_min: int = 30
    login_limit_per_min: int = 10
    request_timeout_s: float = 30.0
    llm_timeout_s: float = 20.0
    bus_max_age_s: int = 300
    min_confidence: float = 0.35
    users: dict = field(default_factory=dict)

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @classmethod
    def from_env(cls) -> Settings:
        env = os.getenv("AEGIS_ENV", "dev").lower()
        if env not in {"dev", "prod"}:
            raise ConfigError("AEGIS_ENV deve ser 'dev' ou 'prod'")
        role = os.getenv("AEGIS_ROLE", "all").lower()
        if role not in {"api", "worker", "all"}:
            raise ConfigError("AEGIS_ROLE deve ser api, worker ou all")
        bus = os.getenv("AEGIS_BUS", "memory").lower()
        if bus not in {"memory", "redis"}:
            raise ConfigError("AEGIS_BUS deve ser memory ou redis")
        redis_url = os.getenv("AEGIS_REDIS_URL", "")
        if bus == "redis" and not redis_url:
            raise ConfigError("AEGIS_REDIS_URL é obrigatório com AEGIS_BUS=redis")
        if env == "prod" and bus == "memory" and role != "all":
            raise ConfigError("Com roles separados é obrigatório usar AEGIS_BUS=redis")

        raw = os.getenv("AEGIS_MASTER_KEY", "")
        if raw:
            try:
                key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
            except Exception as exc:  # noqa: BLE001
                raise ConfigError("AEGIS_MASTER_KEY não é base64 válido") from exc
            if len(key) < 32:
                raise ConfigError("AEGIS_MASTER_KEY precisa ter pelo menos 32 bytes")
        elif env == "prod" or bus == "redis":
            raise ConfigError(
                "AEGIS_MASTER_KEY é obrigatório em produção ou com barramento Redis "
                "(gere com: python scripts/gen_keys.py)"
            )
        else:
            key = secrets.token_bytes(32)
            log.warning("AEGIS_MASTER_KEY ausente: usando chave efêmera (somente dev).")

        try:
            users = json.loads(os.getenv("AEGIS_USERS", "{}"))
        except json.JSONDecodeError as exc:
            raise ConfigError("AEGIS_USERS não é JSON válido") from exc

        chain = tuple(
            n.strip()
            for n in os.getenv("AEGIS_LLM_CHAIN", "").split(",")
            if n.strip() and n.strip() != "extractive"
        )
        return cls(
            env=env,
            role=role,
            master_key=key,
            kb_path=Path(os.getenv("AEGIS_KB_PATH", str(cls.kb_path))),
            audit_dir=Path(os.getenv("AEGIS_AUDIT_DIR", str(cls.audit_dir))),
            bus_backend=bus,
            redis_url=redis_url,
            llm_chain=chain,
            rate_limit_per_min=int(os.getenv("AEGIS_RATE_LIMIT", "30")),
            users=users,
        )
