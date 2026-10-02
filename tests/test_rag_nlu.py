import json
from pathlib import Path

import pytest

from aegis.nlu import analyze
from aegis.rag import KBError, KnowledgeBase
from aegis.security import crypto

KB_PATH = Path(__file__).resolve().parents[1] / "data" / "kb" / "base_conhecimento.json"


def test_kb_loads_and_unique_ids():
    kb = KnowledgeBase.load(KB_PATH)
    assert len(kb.chunks) >= 30 and len({c["id"] for c in kb.chunks}) == len(kb.chunks)


def test_encrypted_kb_roundtrip(tmp_path):
    key = crypto.derive_key(b"m" * 32, "kb")
    enc = tmp_path / "kb.enc"
    enc.write_bytes(crypto.encrypt(key, KB_PATH.read_bytes(), aad=b"aegis-kb"))
    assert len(KnowledgeBase.load(enc, key).chunks) == len(KnowledgeBase.load(KB_PATH).chunks)
    with pytest.raises(Exception):  # noqa: B017
        KnowledgeBase.load(enc, crypto.derive_key(b"x" * 32, "kb"))


def test_invalid_kb_rejected():
    with pytest.raises(KBError):
        KnowledgeBase([{"id": "a"}])


def test_search_ranks_expected():
    kb = KnowledgeBase.load(KB_PATH)
    assert kb.search("Como proteger o barramento Redis Streams?")[0].chunk["id"] == "kb-026"
    assert kb.search("receita de bolo") == []


@pytest.mark.parametrize("text,intent", [
    ("Oi", "saudacao"), ("obrigado!", "agradecimento"), ("ajuda", "ajuda"),
    ("Fui hackeado, e agora?", "incidente"), ("Commitei uma senha no git", "incidente"),
    ("Como funciona TLS?", "duvida_seguranca"), ("preciso de ajuda com docker", "duvida_seguranca"),
])
def test_intents(text, intent):
    assert analyze(text).intent == intent


def test_lang_and_topics():
    r = analyze("How does Docker image scanning work?")
    assert r.lang == "en" and "container" in r.topics


def test_golden_set_is_valid_json():
    g = json.loads((KB_PATH.parents[2] / "eval" / "golden_set.json").read_text())
    ids = {c["id"] for c in json.loads(KB_PATH.read_text())}
    assert all(e in ids for _, exp in g["retrieval"] for e in exp)
