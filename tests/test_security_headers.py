"""Tests for security headers middleware."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core.security_headers import SecurityHeadersMiddleware


def _make_app():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    return TestClient(app)


client = _make_app()


def test_security_headers_present():
    r = client.get("/test")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-XSS-Protection"] == "1; mode=block"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "cdnjs.cloudflare.com" in r.headers["Content-Security-Policy"]
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert r.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"


def test_hsts_not_on_http():
    r = client.get("/test")
    assert "Strict-Transport-Security" not in r.headers


def test_headers_on_every_response():
    r = client.get("/test")
    assert r.status_code == 200
    assert "X-Content-Type-Options" in r.headers
