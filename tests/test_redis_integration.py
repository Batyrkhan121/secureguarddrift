# tests/test_redis_integration.py
"""Tests for cache/ — Redis client, rate limiter, and @cached decorator.

All tests run WITHOUT Redis (graceful fallback to in-memory).
"""

import asyncio
import time

from cache.redis_client import get_redis, connect_redis, close_redis, ping
from cache.rate_limiter import check_rate_async
from cache.cache import cached, invalidate


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Redis client (no Redis → fallback)
# ---------------------------------------------------------------------------

class TestRedisClient:
    def test_get_redis_returns_none_without_connection(self):
        assert get_redis() is None

    def test_connect_returns_none_without_redis(self):
        result = _run(connect_redis())
        assert result is None
        assert get_redis() is None

    def test_close_is_safe_without_connection(self):
        _run(close_redis())  # should not raise

    def test_ping_returns_false_without_redis(self):
        assert _run(ping()) is False


# ---------------------------------------------------------------------------
# Rate limiter (fallback to in-memory)
# ---------------------------------------------------------------------------

class TestRedisRateLimiter:
    def test_allows_within_limit(self):
        async def _test():
            for i in range(5):
                allowed, remaining, reset = await check_rate_async(f"test_rl_{time.time()}:{i}", 10)
                assert allowed is True
                assert remaining >= 0
        _run(_test())

    def test_blocks_over_limit(self):
        async def _test():
            key = f"test_rl_block_{time.time()}"
            for _ in range(3):
                allowed, _, _ = await check_rate_async(key, 3)
            # 4th should be blocked
            allowed, remaining, _ = await check_rate_async(key, 3)
            assert allowed is False
            assert remaining == 0
        _run(_test())

    def test_returns_correct_remaining(self):
        async def _test():
            key = f"test_rl_rem_{time.time()}"
            allowed, remaining, _ = await check_rate_async(key, 5)
            assert allowed is True
            assert remaining == 4
        _run(_test())


# ---------------------------------------------------------------------------
# @cached decorator (fallback — no caching, direct call)
# ---------------------------------------------------------------------------

class TestCachedDecorator:
    def test_cached_calls_function_directly_without_redis(self):
        call_count = 0

        @cached(ttl=60, key_prefix="test_fn")
        async def expensive_fn(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        async def _test():
            result1 = await expensive_fn(5)
            result2 = await expensive_fn(5)
            assert result1 == 10
            assert result2 == 10

        _run(_test())
        # Without Redis, function is called every time (no cache)
        assert call_count == 2

    def test_invalidate_returns_false_without_redis(self):
        result = _run(invalidate("some_prefix", "some_id"))
        assert result is False


# ---------------------------------------------------------------------------
# Integration: rate limiter interface compatibility
# ---------------------------------------------------------------------------

class TestRateLimiterCompatibility:
    def test_same_interface_as_sync(self):
        """check_rate_async returns same (allowed, remaining, reset) tuple."""
        async def _test():
            result = await check_rate_async(f"compat_{time.time()}", 10)
            assert isinstance(result, tuple)
            assert len(result) == 3
            allowed, remaining, reset = result
            assert isinstance(allowed, bool)
            assert isinstance(remaining, int)
            assert isinstance(reset, int)
        _run(_test())
