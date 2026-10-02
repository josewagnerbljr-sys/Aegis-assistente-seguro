"""Gera o hash scrypt de uma senha para AEGIS_USERS. Uso: python scripts/hash_password.py usuario papel"""

import getpass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aegis.security.crypto import hash_password  # noqa: E402

user, role = (sys.argv + ["usuario", "aluno"])[1:3]
pw = getpass.getpass("Senha: ")
print(json.dumps({user: {"hash": hash_password(pw), "role": role}}))
