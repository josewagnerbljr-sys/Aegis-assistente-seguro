"""Compreensão de linguagem natural leve: intenção, tópicos, urgência e idioma."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .text import fold, stem, tokens

_GREET = re.compile(r"^(oi+|ola|opa|e ai|bom dia|boa tarde|boa noite|hello|hi|hey)\b")
_THANKS = re.compile(r"\b(obrigad[oa]|valeu|thanks|thank you|brigad[oa])\b")
_HELP = re.compile(
    r"^\W*(ajuda|help|menu|o que (voce|vc) (faz|pode fazer|sabe)|como (voce )?funciona|what can you do)\W*$"
)
_INCIDENT = [
    re.compile(
        r"\b(fui|fomos|estamos|esta|estao|foi|foram|ficou|meu|minha|nosso|nossa|acabei|acabamos)\b"
        r".{0,40}\b(hackead\w*|invadid\w*|comprometid\w*|vazad\w*|vazou|sequestrad\w*|ransomware|ataque|atacad\w*|criptografad\w*)\b"
    ),
    re.compile(r"\b(commit\w*|subi|push\w*|publiquei|enviei)\b.{0,40}\b(senha|token|chave|segredo|credencial)\b"),
]
_TOPIC_WORDS = {
    "appsec": "owasp sql xss injecao csrf idor vulnerabilidade codigo web sast dast",
    "container": "docker container imagem kubernetes k8s dockerfile runtime compose",
    "pipeline": "pipeline ci cd sast dast sca sbom devsecops github gitlab actions build deploy",
    "cripto": "criptografia aes tls hash chave certificado cifra assinatura gcm",
    "iam": "senha mfa jwt token acesso autenticacao autorizacao rbac privilegio",
    "llm": "llm prompt ia generativa rag alucinacao modelo",
    "incidente": "incidente ransomware vazamento backup forense resposta",
    "rede": "firewall rede segmentacao zero trust barramento mensagem",
}
_TOPICS = {k: {stem(w) for w in v.split()} for k, v in _TOPIC_WORDS.items()}
_EN = {"the", "how", "what", "is", "are", "do", "does", "can", "should", "why", "my", "your", "with"}
_PT = {"o", "a", "que", "como", "para", "de", "uma", "um", "nao", "meu", "minha", "por", "qual", "quais", "voce"}


@dataclass
class NLUResult:
    intent: str  # saudacao | agradecimento | ajuda | incidente | duvida_seguranca
    topics: list[str]
    urgency: str  # normal | alta
    lang: str  # pt | en

    def as_dict(self) -> dict:
        return asdict(self)


def analyze(text: str) -> NLUResult:
    f = fold(text).strip()
    words = f.split()
    pt = sum(w in _PT for w in words)
    lang = "en" if sum(w in _EN for w in words) > pt else "pt"
    toks = set(tokens(text))
    topics = [k for k, v in _TOPICS.items() if toks & v]
    if _HELP.match(f):
        intent = "ajuda"
    elif _GREET.match(f) and len(words) <= 4:
        intent = "saudacao"
    elif _THANKS.search(f) and len(words) <= 5:
        intent = "agradecimento"
    elif any(p.search(f) for p in _INCIDENT):
        return NLUResult("incidente", sorted({*topics, "incidente"}), "alta", lang)
    else:
        intent = "duvida_seguranca"
    return NLUResult(intent, topics, "normal", lang)
