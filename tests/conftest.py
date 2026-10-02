import dataclasses
import os

import pytest
from fastapi.testclient import TestClient

from aegis.config import Settings
from aegis.main import create_app
from aegis.security.crypto import hash_password

PASSWORD = "Senha-de-Teste-123"


@pytest.fixture(scope="session")
def pw_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def settings(tmp_path, pw_hash):
    return dataclasses.replace(
        Settings(),
        master_key=os.urandom(32),
        audit_dir=tmp_path / "audit",
        users={"ana": {"hash": pw_hash, "role": "analista"}, "root": {"hash": pw_hash, "role": "admin"}},
        rate_limit_per_min=1000,
        login_limit_per_min=1000,
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def login(client, user="ana"):
    r = client.post("/v1/auth/token", json={"username": user, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
