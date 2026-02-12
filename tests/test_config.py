# tests/test_config.py
"""Tests for core.config — Application configuration."""

from core.config import AppSettings, DatabaseSettings, CacheSettings


class TestDatabaseSettings:
    """Tests for DatabaseSettings."""

    def test_defaults(self):
        """Default values are correct."""
        s = DatabaseSettings()
        assert s.backend == "sqlite"
        assert s.pool_size == 5
        assert s.max_overflow == 10

    def test_env_override(self, monkeypatch):
        """Environment variables override defaults."""
        monkeypatch.setenv("SECUREGUARD_DB_BACKEND", "postgresql")
        monkeypatch.setenv("SECUREGUARD_DB_URL", "postgresql://localhost/test")
        monkeypatch.setenv("SECUREGUARD_DB_POOL_SIZE", "20")
        s = DatabaseSettings()
        assert s.backend == "postgresql"
        assert s.url == "postgresql://localhost/test"
        assert s.pool_size == 20


class TestCacheSettings:
    """Tests for CacheSettings."""

    def test_defaults(self):
        """Default values are correct."""
        s = CacheSettings()
        assert s.backend == "memory"
        assert s.ttl == 300
        assert s.redis_url == "redis://localhost:6379/0"

    def test_env_override(self, monkeypatch):
        """Environment variables override defaults."""
        monkeypatch.setenv("SECUREGUARD_CACHE_BACKEND", "redis")
        monkeypatch.setenv("SECUREGUARD_CACHE_TTL", "600")
        s = CacheSettings()
        assert s.backend == "redis"
        assert s.ttl == 600


class TestAppSettings:
    """Tests for AppSettings."""

    def test_defaults(self):
        """Default values are correct."""
        s = AppSettings()
        assert s.environment == "development"
        assert s.debug is False

    def test_nested_settings(self):
        """Database and cache settings are nested."""
        s = AppSettings()
        assert isinstance(s.database, DatabaseSettings)
        assert isinstance(s.cache, CacheSettings)
