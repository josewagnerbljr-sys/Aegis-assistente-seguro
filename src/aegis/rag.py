"""Base de conhecimento + recuperação BM25 (implementação própria, sem dependências).

A base pode estar em claro (dev) ou cifrada em repouso com AES-256-GCM (`.enc`).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .security import crypto
from .text import tokens

REQUIRED = {"id", "titulo", "categoria", "conteudo", "passos", "tags"}
K1, B = 1.5, 0.75


class KBError(ValueError):
    pass


@dataclass
class Hit:
    chunk: dict
    score: float
    coverage: float
    confidence: float

    def as_dict(self) -> dict:
        c = self.chunk
        return {
            "id": c["id"],
            "titulo": c["titulo"],
            "categoria": c["categoria"],
            "conteudo": c["conteudo"],
            "passos": c["passos"],
            "fontes": c.get("fontes", []),
            "score": round(self.score, 3),
            "confidence": round(self.confidence, 3),
        }


class KnowledgeBase:
    def __init__(self, chunks: list[dict]) -> None:
        ids = set()
        for c in chunks:
            missing = REQUIRED - c.keys()
            if missing:
                raise KBError(f"chunk {c.get('id')} sem campos: {sorted(missing)}")
            if c["id"] in ids:
                raise KBError(f"id duplicado: {c['id']}")
            ids.add(c["id"])
        self.chunks = chunks
        self._by_id = {c["id"]: c for c in chunks}
        self._tf: list[Counter] = []
        for c in chunks:
            toks = (
                tokens(c["titulo"]) * 3
                + tokens(" ".join(c["tags"])) * 2
                + tokens(c["conteudo"])
                + tokens(" ".join(c["passos"]))
            )
            self._tf.append(Counter(toks))
        self._len = [sum(tf.values()) for tf in self._tf]
        self._avg = sum(self._len) / len(self._len)
        df: Counter = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        n = len(chunks)
        self._idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    @classmethod
    def load(cls, path: Path, enc_key: bytes | None = None) -> KnowledgeBase:
        raw = Path(path).read_bytes()
        if Path(path).suffix == ".enc":
            if enc_key is None:
                raise KBError("base cifrada exige chave")
            raw = crypto.decrypt(enc_key, raw, aad=b"aegis-kb")
        return cls(json.loads(raw))

    def get(self, chunk_id: str) -> dict | None:
        return self._by_id.get(chunk_id)

    def topics(self) -> list[tuple[str, int]]:
        return sorted(Counter(c["categoria"] for c in self.chunks).items())

    def search(self, query: str, topics: list[str] | None = None, k: int = 3) -> list[Hit]:
        q = list(dict.fromkeys(tokens(query)))
        if not q:
            return []
        hits: list[Hit] = []
        for i, c in enumerate(self.chunks):
            tf, norm = self._tf[i], 1 - B + B * self._len[i] / self._avg
            score, matched = 0.0, 0
            for t in q:
                f = tf.get(t, 0)
                if f:
                    matched += 1
                    score += self._idf[t] * f * (K1 + 1) / (f + K1 * norm)
            if not matched:
                continue
            coverage = matched / len(q)
            if topics and c["categoria"] in topics:
                score *= 1.1
            conf = min(1.0, 0.6 * coverage + 0.4 * min(1.0, score / 10))
            if matched < 2 and len(q) >= 2:  # um único termo em comum é evidência fraca
                conf *= 0.6
            hits.append(Hit(c, score, coverage, conf))
        hits.sort(key=lambda h: (h.score, h.coverage), reverse=True)
        return hits[:k]
