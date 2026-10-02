"""Gera a chave-mestra (32 bytes, base64url) e uma senha de Redis. Guarde no cofre, não no Git."""

import base64
import secrets

print("AEGIS_MASTER_KEY=" + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="))
print("REDIS_PASSWORD=" + secrets.token_urlsafe(24))
