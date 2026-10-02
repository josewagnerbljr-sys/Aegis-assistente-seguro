"""Barramento de mensagens seguro.

Cada mensagem trafega como envelope: cabeçalho (tópico, trace, timestamp) em claro e payload
cifrado com AES-256-GCM (cabeçalho como AAD), mais HMAC-SHA256 do conjunto. O HMAC (chave
independente) permite a um intermediário rejeitar lixo sem poder decifrar; o timestamp
limita replay. Backends: memória (dev/testes, mesmo caminho criptográfico) e Redis Streams.
"""

from __future__ import annotations

import abc
import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag

from .security import crypto

log = logging.getLogger("aegis.bus")


class IntegrityError(Exception):
    """Assinatura inválida, adulteração, chave errada ou mensagem expirada (replay)."""


@dataclass(frozen=True)
class Envelope:
    topic: str
    trace_id: str
    payload: dict


Handler = Callable[[Envelope], Awaitable[None]]


class SecureCodec:
    def __init__(self, enc_key: bytes, mac_key: bytes, max_age_s: int = 300) -> None:
        self._enc, self._mac, self.max_age = enc_key, mac_key, max_age_s

    def encode(self, topic: str, trace_id: str, payload: dict) -> bytes:
        ts = int(time.time())
        header = f"{topic}|{trace_id}|{ts}".encode()
        ct = crypto.encrypt(self._enc, json.dumps(payload, separators=(",", ":")).encode(), header)
        sig = crypto.sign(self._mac, header + b"|" + ct)
        return json.dumps(
            {"t": topic, "i": trace_id, "ts": ts, "ct": crypto.b64e(ct), "sig": sig}
        ).encode()

    def decode(self, wire: bytes) -> Envelope:
        try:
            obj = json.loads(wire)
            topic, trace, ts = str(obj["t"]), str(obj["i"]), int(obj["ts"])
            ct = crypto.b64d(obj["ct"])
            header = f"{topic}|{trace}|{ts}".encode()
            if not crypto.verify(self._mac, header + b"|" + ct, str(obj["sig"])):
                raise IntegrityError("assinatura inválida")
            if abs(time.time() - ts) > self.max_age:
                raise IntegrityError("mensagem expirada (possível replay)")
            return Envelope(topic, trace, json.loads(crypto.decrypt(self._enc, ct, header)))
        except IntegrityError:
            raise
        except (InvalidTag, ValueError, KeyError, TypeError) as exc:
            raise IntegrityError("envelope malformado ou adulterado") from exc


class MessageBus(abc.ABC):
    def __init__(self, codec: SecureCodec) -> None:
        self.codec = codec
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)

    async def start(self) -> None:  # noqa: B027
        pass

    async def stop(self) -> None:  # noqa: B027
        pass

    @abc.abstractmethod
    async def publish(self, topic: str, trace_id: str, payload: dict) -> None: ...

    async def _deliver(self, handler: Handler, wire: bytes) -> bool:
        try:
            env = self.codec.decode(wire)
        except IntegrityError as exc:
            log.warning("mensagem descartada: %s", exc)
            return False
        await handler(env)
        return True


class InMemoryBus(MessageBus):
    """Entrega assíncrona no mesmo processo, passando pelo mesmo codec cifrado/assinado."""

    def __init__(self, codec: SecureCodec) -> None:
        super().__init__(codec)
        self._tasks: set[asyncio.Task] = set()

    async def publish(self, topic: str, trace_id: str, payload: dict) -> None:
        wire = self.codec.encode(topic, trace_id, payload)
        for h in self._handlers.get(topic, []):
            task = asyncio.create_task(self._safe(h, wire))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _safe(self, handler: Handler, wire: bytes) -> None:
        try:
            await self._deliver(handler, wire)
        except Exception:
            log.exception("falha no handler")

    async def stop(self) -> None:
        for t in list(self._tasks):
            t.cancel()


class RedisStreamsBus(MessageBus):
    """Redis Streams + consumer groups: entrega at-least-once, balanceamento entre workers e
    dead-letter stream (`aegis:dlq`) para mensagens que falham ou são inválidas."""

    def __init__(self, codec: SecureCodec, url: str, group: str = "aegis") -> None:
        super().__init__(codec)
        import redis.asyncio as aioredis

        self._r = aioredis.from_url(url, decode_responses=False)
        self._group, self._consumer = group, uuid.uuid4().hex[:8]
        self._loops: list[asyncio.Task] = []
        self._running = False

    async def publish(self, topic: str, trace_id: str, payload: dict) -> None:
        wire = self.codec.encode(topic, trace_id, payload)
        await self._r.xadd(f"aegis:{topic}", {"d": wire}, maxlen=10_000, approximate=True)

    async def start(self) -> None:
        import redis.exceptions as rexc

        self._running = True
        for topic in self._handlers:
            try:
                await self._r.xgroup_create(f"aegis:{topic}", self._group, id="0", mkstream=True)
            except rexc.ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
            self._loops.append(asyncio.create_task(self._loop(topic)))

    async def _loop(self, topic: str) -> None:
        stream = f"aegis:{topic}"
        while self._running:
            try:
                resp = await self._r.xreadgroup(
                    self._group, self._consumer, {stream: ">"}, count=10, block=1000
                )
                for _, messages in resp or []:
                    for msg_id, fields in messages:
                        await self._process(topic, stream, msg_id, fields[b"d"])
                if not resp:
                    await asyncio.sleep(0.01)  # cede o loop mesmo se o servidor não bloquear
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("erro no consumidor %s", topic)
                await asyncio.sleep(1)

    async def _process(self, topic: str, stream: str, msg_id: bytes, wire: bytes) -> None:
        ok = True
        for h in self._handlers[topic]:
            try:
                ok = await self._deliver(h, wire) and ok
            except Exception:
                log.exception("handler falhou")
                ok = False
        if not ok:
            await self._r.xadd("aegis:dlq", {"d": wire, "topic": topic}, maxlen=1_000, approximate=True)
        await self._r.xack(stream, self._group, msg_id)

    async def stop(self) -> None:
        self._running = False
        for t in self._loops:
            t.cancel()
        await self._r.aclose()
