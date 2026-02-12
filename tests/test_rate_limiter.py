"""Tests for core/rate_limiter.py — sliding window rate limiter."""

import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.rate_limiter import RateLimitMiddleware, reset_all, WINDOW_SECONDS


@pytest.fixture(autouse=True)
def _clean():
    reset_all()
    yield
    reset_all()


def _make_app(limit: int = 5) -> TestClient:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, user_limit=limit)

    @app.get("/api/test")
    def test_endpoint():
        return {"ok": True}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return TestClient(app)


def test_requests_within_limit():
    client = _make_app(limit=5)
    for _ in range(5):
        r = client.get("/api/test")
        assert r.status_code == 200
        assert "X-RateLimit-Limit" in r.headers
        assert "X-RateLimit-Remaining" in r.headers
        assert "X-RateLimit-Reset" in r.headers


def test_rate_limit_exceeded():
    client = _make_app(limit=5)
    for _ in range(5):
        assert client.get("/api/test").status_code == 200
    r = client.get("/api/test")
    assert r.status_code == 429
    assert r.json()["detail"] == "Too Many Requests"
    assert "Retry-After" in r.headers


def test_health_excluded():
    client = _make_app(limit=1)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").status_code == 200  # no limit


def test_window_reset():
    client = _make_app(limit=3)
    base = time.time()
    with patch("core.rate_limiter.time") as mock_time:
        mock_time.time.return_value = base
        for _ in range(3):
            assert client.get("/api/test").status_code == 200
        assert client.get("/api/test").status_code == 429

        # Advance past the window
        mock_time.time.return_value = base + WINDOW_SECONDS + 1
        assert client.get("/api/test").status_code == 200
