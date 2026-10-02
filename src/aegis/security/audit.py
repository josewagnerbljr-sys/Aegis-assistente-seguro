"""Trilha de auditoria à prova de adulteração: cada linha carrega o HMAC da anterior.

Alterar ou remover uma linha do meio quebra a cadeia (detectável por `verify`).
Truncar o FIM do arquivo não é detectável sem uma âncora externa (SIEM/WORM) — veja docs.
Nunca registra o texto da pergunta, só uma impressão digital (HMAC) e metadados.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .crypto import sign


class AuditLog:
    def __init__(self, path: Path, key: bytes) -> None:
        self.path = Path(path)
        self._key = key
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        self._last = self._load_last()

    def _load_last(self) -> str:
        last = "GENESIS"
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        last = json.loads(line)["mac"]
                    except (ValueError, KeyError):
                        pass
        return last

    def fingerprint(self, text: str) -> str:
        return sign(self._key, text.encode())[:16]

    @staticmethod
    def _canon(rec: dict) -> bytes:
        return json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

    def write(self, event: str, trace_id: str, subject: str, data: dict | None = None) -> None:
        with self._lock:
            rec = {
                "ts": round(time.time(), 3),
                "event": event,
                "trace": trace_id,
                "sub": subject,
                "data": data or {},
                "prev": self._last,
            }
            rec["mac"] = sign(self._key, self._canon(rec))
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self._last = rec["mac"]

    def verify(self) -> tuple[bool, int, int | None]:
        """Retorna (íntegro, nº de registros, nº da linha onde a cadeia quebrou)."""
        prev, count = "GENESIS", 0
        with self.path.open("r", encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    mac = rec.pop("mac")
                except (ValueError, KeyError):
                    return False, count, n
                if rec.get("prev") != prev or sign(self._key, self._canon(rec)) != mac:
                    return False, count, n
                prev, count = mac, count + 1
        return True, count, None
