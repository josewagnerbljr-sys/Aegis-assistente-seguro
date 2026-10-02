"""Normalização e tokenização PT/EN (sem dependências externas)."""

from __future__ import annotations

import re
import unicodedata

_STOP = set(
    ["a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sobre", "entre", "e", "ou", "que", "qual", "quais", "quando", "onde", "como", "porque", "pq", "se", "ao", "aos", "ser", "sao", "foi", "eh", "ter", "tem", "tenho", "fazer", "faco", "faz", "posso", "pode", "preciso", "quero", "gostaria", "me", "meu", "minha", "seu", "sua", "isso", "isto", "esse", "essa", "este", "esta", "aquele", "evitar", "ja", "mais", "muito", "muita", "ainda", "tambem", "so", "mas", "the", "is", "are", "of", "to", "in", "on", "for", "and", "or", "what", "how", "do", "does", "can", "i", "my", "with", "an", "it", "be", "this", "that", "vou", "vai", "usar", "uso", "devo", "deve", "fazem", "sobre", "voce", "vc", "ha"]
)
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)


def fold(s: str) -> str:
    """minúsculas, NFKC, sem acentos e sem caracteres invisíveis."""
    s = unicodedata.normalize("NFKC", s).translate(_ZERO_WIDTH)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def stem(t: str) -> str:
    """Stemming mínimo para plurais PT/EN (suficiente para casar termos técnicos)."""
    if t.endswith("coes") and len(t) > 5:
        return t[:-4] + "cao"
    if t.endswith("oes") and len(t) > 4:
        return t[:-3] + "ao"
    if t.endswith("ns") and len(t) > 4:
        return t[:-2] + "m"
    if t.endswith("s") and not t.endswith("ss") and len(t) > 3:
        return t[:-1]
    return t


def tokens(s: str) -> list[str]:
    return [stem(t) for t in re.findall(r"[a-z0-9]+", fold(s)) if t not in _STOP and len(t) > 1]
