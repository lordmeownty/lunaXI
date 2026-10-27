"""Entra mode: real RS256 tokens signed by a test key."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.security import auth

TENANT, CLIENT = "11111111-2222-3333-4444-555555555555", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _Signing:
    key = KEY.public_key()


class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        return _Signing()


@pytest.fixture(autouse=True)
def entra(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "entra")
    monkeypatch.setattr(settings, "entra_tenant_id", TENANT)
    monkeypatch.setattr(settings, "entra_api_client_id", CLIENT)
    monkeypatch.setattr(auth._JWKS, "client", classmethod(lambda cls: _FakeJWKS()))


def token(roles, aud=f"api://{CLIENT}", tid=TENANT, exp=3600):
    now = int(time.time())
    return jwt.encode({"aud": aud, "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0", "tid": tid, "oid": "o", "name": "Test User",
                       "preferred_username": "u@contoso.example", "roles": roles, "iat": now, "nbf": now, "exp": now + exp}, KEY, algorithm="RS256")


c = TestClient(app)


def test_requires_token():
    assert c.get("/api/matches").status_code == 401


def test_director_token_and_view_as():
    h = {"Authorization": f"Bearer {token(['Luna.Director'])}"}
    assert c.get("/api/me", headers=h).json()["primary_role"] == "Luna.Director"
    assert c.get("/api/control-room", headers=h | {"X-View-As": "Luna.Fan"}).status_code == 403


def test_demo_header_ignored_in_entra_mode():
    assert c.get("/api/control-room", headers={"Authorization": f"Bearer {token(['Luna.Fan'])}", "X-Demo-Role": "Luna.Director"}).status_code == 403


@pytest.mark.parametrize("kw", [{"aud": "api://someone-else"}, {"tid": "other-tenant"}, {"exp": -120}])
def test_bad_tokens_rejected(kw):
    assert c.get("/api/me", headers={"Authorization": f"Bearer {token(['Luna.Admin'], **kw)}"}).status_code == 401
