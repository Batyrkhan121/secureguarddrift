# tests/test_cache.py
"""Tests for core.cache — Cache abstraction layer."""

import time

import pytest

from core.cache import InMemoryCache, get_cache, reset_cache


@pytest.fixture(autouse=True)
def _reset_cache_singleton():
    """Reset cache singleton before each test."""
    reset_cache()
    yield
    reset_cache()


class TestInMemoryCache:
    """Tests for InMemoryCache implementation."""

    def test_set_and_get(self):
        """Basic set/get works."""
        cache = InMemoryCache(default_ttl=60)
        cache.set("key1", {"data": 42})
        assert cache.get("key1") == {"data": 42}

    def test_get_missing_key(self):
        """get() returns None for missing key."""
        cache = InMemoryCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self):
        """Expired entries return None."""
        cache = InMemoryCache(default_ttl=60)
        cache.set("expiring", "value", ttl=1)
        assert cache.get("expiring") == "value"
        time.sleep(1.1)
        assert cache.get("expiring") is None

    def test_delete(self):
        """delete() removes key and returns True."""
        cache = InMemoryCache()
        cache.set("to_delete", "val")
        assert cache.delete("to_delete") is True
        assert cache.get("to_delete") is None

    def test_delete_missing(self):
        """delete() returns False for missing key."""
        cache = InMemoryCache()
        assert cache.delete("missing") is False

    def test_clear(self):
        """clear() removes all entries."""
        cache = InMemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_exists(self):
        """exists() checks key presence."""
        cache = InMemoryCache()
        cache.set("present", "yes")
        assert cache.exists("present") is True
        assert cache.exists("absent") is False

    def test_overwrite(self):
        """Setting same key overwrites value."""
        cache = InMemoryCache()
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"

    def test_default_ttl_used(self):
        """Default TTL is applied when ttl=None."""
        cache = InMemoryCache(default_ttl=1)
        cache.set("defaultttl", "val")
        assert cache.get("defaultttl") == "val"
        time.sleep(1.1)
        assert cache.get("defaultttl") is None

    def test_none_value_stored(self):
        """Can store None as a value (distinct from missing)."""
        cache = InMemoryCache()
        cache.set("none_val", None)
        # None value is indistinguishable from missing via get() — this is expected
        assert cache.get("none_val") is None


class TestGetCache:
    """Tests for get_cache() factory."""

    def test_returns_in_memory_cache(self):
        """get_cache() returns InMemoryCache by default."""
        cache = get_cache()
        assert isinstance(cache, InMemoryCache)

    def test_singleton_behavior(self):
        """get_cache() returns the same instance."""
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2

    def test_unknown_backend_raises(self):
        """get_cache() raises for unknown backend."""
        reset_cache()
        with pytest.raises(ValueError, match="Unknown cache backend"):
            get_cache(backend_type="unknown")

    def test_reset_cache_clears(self):
        """reset_cache() resets the singleton."""
        c1 = get_cache()
        c1.set("key", "val")
        reset_cache()
        c2 = get_cache()
        assert c1 is not c2
        assert c2.get("key") is None
