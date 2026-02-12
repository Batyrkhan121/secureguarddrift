# core/cache.py
"""Cache abstraction layer for SecureGuard Drift.

Provides a backend-agnostic caching interface.
Default backend: InMemoryCache (backward-compatible, no external deps).
Future backend: RedisCache (for production multi-instance deployments).

Usage:
    from core.cache import get_cache

    cache = get_cache()
    cache.set("key", {"data": 1}, ttl=60)
    value = cache.get("key")
"""

from __future__ import annotations

import threading
import time
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """Protocol for cache backends."""

    def get(self, key: str) -> Any | None:
        """Get value by key. Returns None if not found or expired."""
        ...

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value with optional TTL (seconds)."""
        ...

    def delete(self, key: str) -> bool:
        """Delete key. Returns True if key existed."""
        ...

    def clear(self) -> None:
        """Clear all entries."""
        ...

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        ...


class InMemoryCache:
    """Thread-safe in-memory cache with TTL support.

    Suitable for single-instance deployments (default).
    """

    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, tuple[Any, float | None]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """Get value by key. Returns None if not found or expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at is not None and time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value with optional TTL (seconds). Uses default_ttl if None."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.time() + effective_ttl if effective_ttl > 0 else None
        with self._lock:
            self._store[key] = (value, expires_at)

    def delete(self, key: str) -> bool:
        """Delete key. Returns True if key existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._store.clear()

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None


# Singleton cache instance
_cache_instance: InMemoryCache | None = None
_cache_lock = threading.Lock()


def get_cache(backend_type: str = "memory", **kwargs) -> InMemoryCache:
    """Get the cache singleton.

    Args:
        backend_type: Cache backend type (default: "memory")
        **kwargs: Backend-specific configuration

    Returns:
        Cache backend instance
    """
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                if backend_type == "memory":
                    _cache_instance = InMemoryCache(**kwargs)
                else:
                    raise ValueError(
                        f"Unknown cache backend: {backend_type}. "
                        f"Available: ['memory']. "
                        f"Install redis extras for Redis support."
                    )
    return _cache_instance


def reset_cache() -> None:
    """Reset the cache singleton (for testing)."""
    global _cache_instance
    with _cache_lock:
        if _cache_instance is not None:
            _cache_instance.clear()
        _cache_instance = None
