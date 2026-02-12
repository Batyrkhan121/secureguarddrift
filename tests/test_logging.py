"""Tests for core/logging.py — structured JSON logging."""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.logging import (
    JSONFormatter,
    RequestLoggingMiddleware,
    get_logger,
    request_ctx,
    setup_logging,
)


@pytest.fixture()
def _reset_root():
    root = logging.getLogger()
    original = root.handlers[:]
    yield
    root.handlers = original


def test_json_formatter_output():
    fmt = JSONFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "hello world", (), None)
    out = json.loads(fmt.format(record))
    assert out["level"] == "INFO"
    assert out["message"] == "hello world"
    assert "timestamp" in out


def test_secret_filter():
    fmt = JSONFormatter()
    record = logging.LogRecord("test", logging.INFO, "", 0, "token=abc123 ok", (), None)
    out = json.loads(fmt.format(record))
    assert "abc123" not in out["message"]
    assert "***" in out["message"]


def test_request_id_header():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/ping")
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers
    # UUID4 format
    rid = r.headers["X-Request-ID"]
    assert len(rid) == 36


def test_request_id_propagated():
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ctx")
    def ctx_endpoint():
        ctx = request_ctx.get()
        return {"request_id": ctx.get("request_id")}

    client = TestClient(app)
    r = client.get("/ctx")
    data = r.json()
    assert data["request_id"] == r.headers["X-Request-ID"]


def test_get_logger():
    logger = get_logger("mymodule")
    assert logger.name == "mymodule"


def test_setup_logging(_reset_root):
    setup_logging("DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
