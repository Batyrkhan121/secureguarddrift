# cache/rate_limiter.py
"""Redis-based sliding window rate limiter with in-memory fallback.

Uses sorted sets (ZADD/ZREMRANGEBYSCORE/ZCARD) for atomic sliding window.
Falls back to core.rate_limiter if Redis is unavailable.
"""

from __future__ import annotations

import time

from cache.redis_client import get_redis
from core.rate_limiter import WINDOW_SECONDS
from core.rate_limiter import check_rate as _inmemory_check_rate


async def check_rate_async(key: str, limit: int, now: float | None = None) -> tuple[bool, int, int]:
    """Async rate check: Redis sorted-set sliding window with in-memory fallback.

    Returns (allowed, remaining, reset_epoch).
    """
    if now is None:
        now = time.time()

    redis = get_redis()
    if redis is None:
        return _inmemory_check_rate(key, limit, now)

    try:
        window_start = now - WINDOW_SECONDS
        reset = int(now) + WINDOW_SECONDS

        pipe = redis.pipeline(transaction=True)
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, WINDOW_SECONDS + 1)
        results = await pipe.execute()

        count = results[1]  # ZCARD result (before ZADD)
        if count >= limit:
            # Over limit — remove the ZADD we just did
            await redis.zrem(key, str(now))
            return False, 0, reset

        remaining = limit - count - 1
        return True, remaining, reset
    except Exception:
        # Redis error — fall back to in-memory
        return _inmemory_check_rate(key, limit, now)
