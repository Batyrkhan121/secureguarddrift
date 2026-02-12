# core/config.py
"""Centralized configuration for SecureGuard Drift.

Supports environment-based configuration for database backend selection.
Default: SQLite (backward-compatible with existing deployment).
"""

import os
from typing import Literal

from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration.

    Environment variables:
        SECUREGUARD_DB_BACKEND: "sqlite" or "postgresql" (default: sqlite)
        SECUREGUARD_DB_URL: database URL (default: sqlite:///data/snapshots.db)
        SECUREGUARD_DB_POOL_SIZE: connection pool size (default: 5)
        SECUREGUARD_DB_MAX_OVERFLOW: max overflow connections (default: 10)
    """

    backend: Literal["sqlite", "postgresql"] = "sqlite"
    url: str = ""
    pool_size: int = 5
    max_overflow: int = 10

    model_config = {"env_prefix": "SECUREGUARD_DB_"}


class CacheSettings(BaseSettings):
    """Cache configuration.

    Environment variables:
        SECUREGUARD_CACHE_BACKEND: "memory" or "redis" (default: memory)
        SECUREGUARD_CACHE_REDIS_URL: Redis URL (default: redis://localhost:6379/0)
        SECUREGUARD_CACHE_TTL: default TTL in seconds (default: 300)
    """

    backend: Literal["memory", "redis"] = "memory"
    redis_url: str = "redis://localhost:6379/0"
    ttl: int = 300

    model_config = {"env_prefix": "SECUREGUARD_CACHE_"}


class AppSettings(BaseSettings):
    """Application-level configuration."""

    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    data_dir: str = os.path.join(os.path.dirname(__file__), "..", "data")

    database: DatabaseSettings = DatabaseSettings()
    cache: CacheSettings = CacheSettings()

    model_config = {"env_prefix": "SECUREGUARD_"}


# Singleton instance — importable from anywhere
settings = AppSettings()
