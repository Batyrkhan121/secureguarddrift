"""Tests for POST /api/auth/login endpoint."""

import pytest
from fastapi.testclient import TestClient
from api.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_login_success(client):
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"})
    assert r.status_code == 200
    d = r.json()
    assert "token" in d
    assert d["user"]["email"] == "admin@demo.com"
    assert d["user"]["role"] == "admin"


def test_login_viewer(client):
    r = client.post("/api/auth/login", json={"email": "viewer@demo.com", "password": "viewer123"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "viewer"


def test_login_invalid_credentials(client):
    r = client.post("/api/auth/login", json={"email": "bad@user.com", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid credentials"


def test_login_token_is_valid_jwt(client):
    r = client.post("/api/auth/login", json={"email": "admin@demo.com", "password": "admin123"})
    token = r.json()["token"]
    from auth.jwt_handler import jwt_handler
    payload = jwt_handler.verify_token(token)
    assert payload["email"] == "admin@demo.com"
    assert payload["role"] == "admin"
    assert payload["tenant_id"] == "demo"
