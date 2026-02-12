# cache/cache.py
"""@cached decorator for async API response caching via Redis.

Falls back to direct function call if Redis is unavailable.
"""

from __future__ import annotations

import functools
import json
import logging
from typing import Any

from cache.redis_client import get_redis

logger = logging.getLogger(__name__)


def cached(ttl: int = 60, key_prefix: str = "cache"):
    """Decorator that caches async function results in Redis.

    Key format: ``{key_prefix}:{arg1}:{arg2}:...``
    """

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            redis = get_redis()
            if redis is None:
                return await fn(*args, **kwargs)

            parts = [key_prefix] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = ":".join(parts)

            try:
                hit = await redis.get(cache_key)
                if hit is not None:
                    return json.loads(hit)
            except Exception:
                pass

            result = await fn(*args, **kwargs)

            try:
                await redis.set(cache_key, json.dumps(result, default=str), ex=ttl)
            except Exception:
                pass

            return result

        return wrapper

    return decorator


async def invalidate(key_prefix: str, *args: Any) -> bool:
    """Delete a cached key. Returns True if deleted."""
    redis = get_redis()
    if redis is None:
        return False
    parts = [key_prefix] + [str(a) for a in args]
    cache_key = ":".join(parts)
    try:
        return bool(await redis.delete(cache_key))
    except Exception:
        return False
