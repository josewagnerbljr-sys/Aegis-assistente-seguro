"""DLP: mascara dados pessoais e segredos antes de enviar ao modelo/logs e na saída."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("chave_privada", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)")),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
]
_ASSIGN = re.compile(
    r"(?i)\b(password|passwd|senha|secret|token|api[_-]?key|chave)\b(\s*[:=]\s*)['\"]?([^\s'\",;]{6,})"
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_PHONE = re.compile(r"(?<!\d)(?:\+55\s?)?\(?\d{2}\)?\s?9?\d{4}-\d{4}(?!\d)")

SECRET_TYPES = {"chave_privada", "aws_key", "github_token", "api_key", "jwt", "segredo"}


@dataclass
class Redaction:
    text: str
    types: list[str] = field(default_factory=list)


def valid_cpf(raw: str) -> bool:
    d = [int(c) for c in raw if c.isdigit()]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for i in (9, 10):
        s = sum(d[j] * (i + 1 - j) for j in range(i))
        if d[i] != (s * 10 % 11) % 10:
            return False
    return True


def luhn(raw: str) -> bool:
    d = [int(c) for c in raw if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, n in enumerate(reversed(d)):
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def redact(text: str) -> Redaction:
    found: set[str] = set()

    def sub(kind: str, pattern: re.Pattern[str], label: str, check=None) -> None:
        nonlocal text

        def repl(m: re.Match[str]) -> str:
            if check is not None and not check(m.group(0)):
                return m.group(0)
            found.add(kind)
            return label

        text = pattern.sub(repl, text)

    for kind, pat in _SECRET_PATTERNS:
        sub(kind, pat, "[SEGREDO]")

    def assign(m: re.Match[str]) -> str:
        found.add("segredo")
        return f"{m.group(1)}{m.group(2)}[SEGREDO]"

    text = _ASSIGN.sub(assign, text)
    sub("email", _EMAIL, "[EMAIL]")
    sub("cpf", _CPF, "[CPF]", valid_cpf)
    sub("cartao", _CARD, "[CARTAO]", luhn)
    sub("telefone", _PHONE, "[TELEFONE]")
    return Redaction(text=text, types=sorted(found))
