"""Guardrails de entrada: normalização, limites, prompt injection e pedidos ofensivos.

Camada heurística (barata, determinística). NÃO é a única defesa contra prompt injection:
o isolamento estrutural do contexto no prompt, a exigência de citações e o DLP de saída
formam as camadas seguintes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..text import fold

_INJECTION = [
    r"ignor\w* (todas? )?(as |os )?(instrucoes|prompts?)( anteriores| previas)?",
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"(desconsidere|esqueca|desobedeca|descarte) (tudo|todas|as|suas|seu)\b.{0,30}(instrucoes|regras|prompt|acima|anterior)",
    r"(revele|mostre|exiba|imprima|repita|vaze|reveal|show|print|repeat|leak|dump).{0,20}\b(seu|sua|teu|your)\b (system |sistema )?(prompt|instruc\w+|regras|rules|instructions)",
    r"(voce|you) (agora )?(e|eh|are|now)( now)? .{0,20}(dan|sem restricoes|unrestricted|jailbroken)",
    r"\b(jailbreak|modo desenvolvedor|developer mode|dan mode)\b",
    r"(finja|pretend|act as|aja como|atue como|simule) .{0,30}(sem (filtros|restricoes|regras)|no (filters|restrictions|rules)|administrador|admin|root)",
    r"</?(system|assistant|instructions?|contexto|context)>",
    r"\[\[?(system|inst)\]?\]",
]
_OFFENSIVE = [
    r"\b(criar|crie|fazer|faca|escrever|escreva|gerar|gere|desenvolver|desenvolva|programar|programe|write|create|build|make|generate) (um |uma |o |a |me |para mim )*(\w+ )?(ransomware|malware|virus|keylogger|botnet|trojan|rootkit|exploit|backdoor|spyware)\b",
    r"\bcomo (eu )?(posso )?(invadir|hackear|roubar|burlar)\b",
    r"\bhow (do i|to|can i) (hack|break into|steal|crack|ddos|bypass (the )?(login|auth\w*))\b",
]
_INJ = [re.compile(p) for p in _INJECTION]
_OFF = [re.compile(p) for p in _OFFENSIVE]
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class InputVerdict:
    blocked: bool
    text: str = ""
    reason: str = ""
    flags: list[str] = field(default_factory=list)


def check_input(text: str, max_chars: int) -> InputVerdict:
    if not isinstance(text, str) or not text.strip():
        return InputVerdict(True, reason="empty")
    if len(text) > max_chars:
        return InputVerdict(True, reason="too_long")
    clean = _CTRL.sub(" ", text).strip()
    folded = fold(clean)  # remove acentos, NFKC e caracteres invisíveis (anti-ofuscação)
    if any(p.search(folded) for p in _INJ):
        return InputVerdict(True, reason="prompt_injection")
    if any(p.search(folded) for p in _OFF):
        return InputVerdict(True, reason="offensive_request")
    return InputVerdict(False, text=clean)
