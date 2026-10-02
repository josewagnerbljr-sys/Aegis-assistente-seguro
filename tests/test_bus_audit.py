import asyncio
import json
import time

import pytest

from aegis.bus import InMemoryBus, IntegrityError, SecureCodec
from aegis.security import crypto
from aegis.security.audit import AuditLog


def codec(seed=b"a", age=300):
    ring = crypto.KeyRing.from_master(seed * 32)
    return SecureCodec(ring.bus_enc, ring.bus_mac, age)


def test_codec_roundtrip_and_confidentiality():
    c = codec()
    wire = c.encode("t", "id1", {"pergunta": "meu segredo"})
    assert b"meu segredo" not in wire
    assert c.decode(wire).payload == {"pergunta": "meu segredo"}


def test_tamper_header_and_wrong_key():
    c = codec()
    obj = json.loads(c.encode("t", "id1", {"a": 1}))
    obj["t"] = "outro"
    with pytest.raises(IntegrityError):
        c.decode(json.dumps(obj).encode())
    with pytest.raises(IntegrityError):
        codec(b"b").decode(c.encode("t", "id1", {"a": 1}))
    with pytest.raises(IntegrityError):
        c.decode(b"lixo")


def test_replay_window():
    c = codec(age=1)
    wire = c.encode("t", "i", {})
    time.sleep(2.1)
    with pytest.raises(IntegrityError):
        c.decode(wire)


async def test_inmemory_bus_delivers_and_drops_invalid():
    got = []
    bus = InMemoryBus(codec())

    async def h(env):
        got.append(env.payload)

    bus.subscribe("x", h)
    await bus.publish("x", "1", {"ok": True})
    await asyncio.sleep(0.05)
    assert got == [{"ok": True}]
    # entrega direta de mensagem forjada é descartada
    assert await bus._deliver(h, codec(b"z").encode("x", "2", {"evil": 1})) is False


def test_audit_chain_detects_tamper(tmp_path):
    key = b"k" * 32
    log = AuditLog(tmp_path / "a.jsonl", key)
    for i in range(5):
        log.write("ev", f"t{i}", "u", {"i": i})
    assert log.verify() == (True, 5, None)
    lines = (tmp_path / "a.jsonl").read_text().splitlines()
    rec = json.loads(lines[2])
    rec["data"]["i"] = 99
    lines[2] = json.dumps(rec)
    (tmp_path / "a.jsonl").write_text("\n".join(lines) + "\n")
    ok, _, bad = AuditLog(tmp_path / "a.jsonl", key).verify()
    assert not ok and bad == 3


def test_audit_never_stores_question(tmp_path):
    log = AuditLog(tmp_path / "a.jsonl", b"k" * 32)
    log.write("answered", "t", "u", {"q": log.fingerprint("minha pergunta secreta")})
    assert "secreta" not in (tmp_path / "a.jsonl").read_text()
