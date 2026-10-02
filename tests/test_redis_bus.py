import asyncio
import os

import pytest

fakeredis = pytest.importorskip("fakeredis")

from aegis.bus import RedisStreamsBus, SecureCodec  # noqa: E402
from aegis.security import crypto  # noqa: E402


async def test_redis_streams_roundtrip_and_dlq(monkeypatch):
    server = fakeredis.FakeServer()
    import redis.asyncio as aioredis

    monkeypatch.setattr(aioredis, "from_url", lambda url, **kw: fakeredis.FakeAsyncRedis(server=server, **kw))
    ring = crypto.KeyRing.from_master(os.urandom(32))
    bus = RedisStreamsBus(SecureCodec(ring.bus_enc, ring.bus_mac), "redis://x")
    got = []

    async def h(env):
        got.append(env.payload)

    bus.subscribe("t", h)
    await bus.start()
    await bus.publish("t", "1", {"a": 1})
    for _ in range(40):
        if got:
            break
        await asyncio.sleep(0.05)
    assert got == [{"a": 1}]
    # mensagem forjada vai para a DLQ e não chega ao handler
    await bus._r.xadd("aegis:t", {"d": b"lixo"})
    await asyncio.sleep(1.5)
    assert await bus._r.xlen("aegis:dlq") == 1 and len(got) == 1
    await bus.stop()
