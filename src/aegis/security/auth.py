"""Autenticação (JWT HS256 de vida curta) e autorização por papel (RBAC)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

import jwt

from .crypto import DUMMY_HASH, verify_password

ROLES = {"aluno": 1, "analista": 2, "admin": 3}


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    sub: str
    role: str

    def has(self, minimum: str) -> bool:
        return ROLES.get(self.role, 0) >= ROLES[minimum]


class AuthService:
    def __init__(self, users: dict, key: bytes, issuer: str, audience: str, ttl: int) -> None:
        self.users, self._key = users, key
        self.issuer, self.audience, self.ttl = issuer, audience, ttl

    def login(self, username: str, password: str) -> str | None:
        user = self.users.get(username)
        ok = verify_password(password, user["hash"] if user else DUMMY_HASH)
        if not (user and ok) or user.get("role") not in ROLES:
            return None
        now = int(time.time())
        claims = {
            "sub": username,
            "role": user["role"],
            "iss": self.issuer,
            "aud": self.audience,
            "iat": now,
            "exp": now + self.ttl,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(claims, self._key, algorithm="HS256")

    def decode(self, token: str) -> Principal:
        try:
            c = jwt.decode(
                token,
                self._key,
                algorithms=["HS256"],  # algoritmo fixo no servidor; "none" é rejeitado
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthError("token inválido") from exc
        if c.get("role") not in ROLES:
            raise AuthError("papel inválido")
        return Principal(sub=c["sub"], role=c["role"])
