# cache/redis_client.py
"""Async Redis client with connection pool and graceful degradation.

If Redis is unavailable, all operations fall back to in-memory (core.cache).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis: Redis | None = None


async def connect_redis() -> Redis | None:
    """Create a Redis connection pool. Returns None if unavailable."""
    global _redis
    try:
        from redis.asyncio import from_url

        _redis = from_url(REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("Redis connected: %s", REDIS_URL)
        return _redis
    except Exception:
        logger.warning("Redis unavailable at %s — using in-memory fallback", REDIS_URL)
        _redis = None
        return None


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


def get_redis() -> Redis | None:
    """Return the current Redis instance (or None if unavailable)."""
    return _redis


async def ping() -> bool:
    """Health check: return True if Redis responds to PING."""
    if _redis is None:
        return False
    try:
        return await _redis.ping()
    except Exception:
        return False
