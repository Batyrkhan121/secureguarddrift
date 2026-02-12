"""In-memory sliding window rate limiter with FastAPI middleware."""

import threading
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Default limits (overridable)
DEFAULT_USER_LIMIT = 100  # requests per window
DEFAULT_TENANT_LIMIT = 1000
WINDOW_SECONDS = 60
CLEANUP_INTERVAL = 300  # 5 minutes

_lock = threading.Lock()
_buckets: dict[str, list[float]] = {}
_last_cleanup: float = 0.0


def _cleanup() -> None:
    """Remove timestamps older than the window."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    cutoff = now - WINDOW_SECONDS
    stale = [k for k, v in _buckets.items() if not v or v[-1] < cutoff]
    for k in stale:
        del _buckets[k]


def _count(key: str, now: float) -> int:
    """Count requests in the current window for *key*."""
    ts = _buckets.get(key, [])
    cutoff = now - WINDOW_SECONDS
    # Remove expired entries from the front
    while ts and ts[0] <= cutoff:
        ts.pop(0)
    return len(ts)


def _record(key: str, now: float) -> None:
    _buckets.setdefault(key, []).append(now)


def check_rate(key: str, limit: int, now: float | None = None) -> tuple[bool, int, int]:
    """Return (allowed, remaining, reset_epoch). Thread-safe."""
    if now is None:
        now = time.time()
    with _lock:
        _cleanup()
        count = _count(key, now)
        reset = int(now) + WINDOW_SECONDS
        if count >= limit:
            return False, 0, reset
        _record(key, now)
        return True, limit - count - 1, reset


def reset_all() -> None:
    """Clear all buckets (useful in tests)."""
    with _lock:
        _buckets.clear()


EXCLUDED_PREFIXES = ("/api/health", "/static")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces per-user rate limits."""

    def __init__(self, app, user_limit: int = DEFAULT_USER_LIMIT,
                 tenant_limit: int = DEFAULT_TENANT_LIMIT):
        super().__init__(app)
        self.user_limit = user_limit
        self.tenant_limit = tenant_limit

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in EXCLUDED_PREFIXES):
            return await call_next(request)

        user = getattr(request.state, "user", None) if hasattr(request, "state") else None
        uid = (user or {}).get("user_id") or request.client.host if request.client else "anon"
        tenant = (user or {}).get("tenant_id")

        now = time.time()
        allowed, remaining, reset = check_rate(f"user:{uid}", self.user_limit, now)
        if not allowed:
            return self._rate_response(self.user_limit, remaining, reset)

        if tenant:
            t_ok, t_rem, t_reset = check_rate(f"tenant:{tenant}", self.tenant_limit, now)
            if not t_ok:
                return self._rate_response(self.tenant_limit, t_rem, t_reset)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.user_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        return response

    @staticmethod
    def _rate_response(limit: int, remaining: int, reset: int):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too Many Requests"},
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset),
                "Retry-After": str(WINDOW_SECONDS),
            },
        )
