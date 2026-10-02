import pytest
from cryptography.exceptions import InvalidTag

from aegis.security import crypto


def test_roundtrip_and_aad():
    k = crypto.derive_key(b"m" * 32, "x")
    blob = crypto.encrypt(k, b"segredo", b"ctx")
    assert crypto.decrypt(k, blob, b"ctx") == b"segredo"
    with pytest.raises(InvalidTag):
        crypto.decrypt(k, blob, b"outro-contexto")


def test_tamper_detected():
    k = crypto.derive_key(b"m" * 32, "x")
    blob = bytearray(crypto.encrypt(k, b"abc"))
    blob[-1] ^= 1
    with pytest.raises(InvalidTag):
        crypto.decrypt(k, bytes(blob))


def test_nonce_unique():
    k = crypto.derive_key(b"m" * 32, "x")
    assert crypto.encrypt(k, b"a")[:12] != crypto.encrypt(k, b"a")[:12]


def test_keyring_separation():
    ring = crypto.KeyRing.from_master(b"m" * 32)
    assert len({ring.bus_enc, ring.bus_mac, ring.kb, ring.audit, ring.jwt}) == 5


def test_password_hash():
    h = crypto.hash_password("abc", n=2**10)
    assert crypto.verify_password("abc", h)
    assert not crypto.verify_password("abd", h)
    assert not crypto.verify_password("abc", "lixo")
    assert h != crypto.hash_password("abc", n=2**10)  # sal único
