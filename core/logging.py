"""Structured JSON logging with request context propagation."""

import contextvars
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

request_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("request_ctx", default={})

_SECRET_RE = re.compile(r"(token|password|secret|key)([\s=:]+)\S+", re.IGNORECASE)
_DEV = os.getenv("ENV", "development") == "development"


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = request_ctx.get()
        msg = _SECRET_RE.sub(r"\1\2***", record.getMessage())
        obj = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "message": msg,
            "logger": record.name,
            "request_id": ctx.get("request_id"),
            "user_id": ctx.get("user_id"),
            "tenant_id": ctx.get("tenant_id"),
        }
        if hasattr(record, "duration_ms"):
            obj["duration_ms"] = record.duration_ms
        if record.exc_info and record.exc_info[0]:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj, indent=2 if _DEV else None, default=str)


def setup_logging(level: str | None = None) -> None:
    """Configure root logger with JSON handler."""
    lvl = level or os.getenv("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    root.setLevel(getattr(logging, lvl.upper(), logging.INFO))
    if not any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, JSONFormatter) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger that inherits the JSON formatter from root."""
    return logging.getLogger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assign request_id, propagate context, add X-Request-ID header."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        user = getattr(request.state, "user", None) or {}
        ctx = {"request_id": rid, "user_id": user.get("user_id"), "tenant_id": user.get("tenant_id")}
        request.state.request_id = rid
        token = request_ctx.set(ctx)
        try:
            response = await call_next(request)
        finally:
            request_ctx.reset(token)
        response.headers["X-Request-ID"] = rid
        return response
