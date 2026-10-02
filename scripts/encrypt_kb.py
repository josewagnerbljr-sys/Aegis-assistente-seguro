"""Cifra a base de conhecimento em repouso (AES-256-GCM, chave derivada por HKDF).

Uso: AEGIS_MASTER_KEY=... python scripts/encrypt_kb.py data/kb/base_conhecimento.json data/kb/base.enc
Depois aponte AEGIS_KB_PATH para o .enc e remova o JSON em claro do ambiente de produção.
"""

import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aegis.security import crypto  # noqa: E402

raw = os.environ["AEGIS_MASTER_KEY"]
master = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
key = crypto.KeyRing.from_master(master).kb
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
dst.write_bytes(crypto.encrypt(key, src.read_bytes(), aad=b"aegis-kb"))
os.chmod(dst, 0o600)
print(f"cifrado: {dst} ({dst.stat().st_size} bytes)")
