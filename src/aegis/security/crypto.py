"""Primitivas criptográficas (sempre via biblioteca `cryptography`/stdlib; nada artesanal).

Hierarquia de chaves: uma chave-mestra (32+ bytes, vinda do cofre/ambiente) gera
subchaves independentes por finalidade usando HKDF-SHA256. Comprometer a subchave
do barramento não revela a do KB, do JWT nem da trilha de auditoria.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

NONCE_LEN = 12  # 96 bits, recomendado para AES-GCM


def derive_key(master: bytes, purpose: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=f"aegis/v1/{purpose}".encode()
    ).derive(master)


@dataclass(frozen=True)
class KeyRing:
    bus_enc: bytes
    bus_mac: bytes
    kb: bytes
    audit: bytes
    jwt: bytes
    canary: str

    @classmethod
    def from_master(cls, master: bytes) -> KeyRing:
        return cls(
            bus_enc=derive_key(master, "bus-enc"),
            bus_mac=derive_key(master, "bus-mac"),
            kb=derive_key(master, "kb"),
            audit=derive_key(master, "audit"),
            jwt=derive_key(master, "jwt"),
            canary="CNR-" + derive_key(master, "canary").hex()[:20],
        )


def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """AES-256-GCM. Retorna nonce || ciphertext||tag. Nonce aleatório novo a cada chamada."""
    nonce = os.urandom(NONCE_LEN)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)


def decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    """Levanta cryptography.exceptions.InvalidTag se houver adulteração ou chave errada."""
    return AESGCM(key).decrypt(blob[:NONCE_LEN], blob[NONCE_LEN:], aad)


def sign(key: bytes, data: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def verify(key: bytes, data: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign(key, data), signature)


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


# --- senhas: scrypt (stdlib), formato auto-descritivo para permitir migração de custo ---
_N, _R, _P = 2**15, 8, 1
_MAXMEM = 128 * 1024 * 1024


def hash_password(password: str, *, n: int = _N, r: int = _R, p: int = _P) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=_MAXMEM)
    return f"scrypt${n}${r}${p}${b64e(salt)}${b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, dk = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(
            password.encode(), salt=b64d(salt), n=int(n), r=int(r), p=int(p), maxmem=_MAXMEM
        )
        return hmac.compare_digest(calc, b64d(dk))
    except (ValueError, TypeError):
        return False


# Hash "isca": iguala o tempo de resposta do login para usuários inexistentes.
DUMMY_HASH = hash_password("aegis-dummy-password")
