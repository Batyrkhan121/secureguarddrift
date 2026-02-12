# core/database.py
"""Database abstraction layer for SecureGuard Drift.

Provides a backend-agnostic interface for database operations.
Default backend: SQLite (backward-compatible).
Future backend: PostgreSQL (via dual-write migration pattern).

Usage:
    from core.database import get_backend

    backend = get_backend("/path/to/db")
    with backend.connection() as conn:
        conn.execute("SELECT 1")
"""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConnectionLike(Protocol):
    """Protocol for database connections (sqlite3.Connection compatible)."""

    def execute(self, sql: str, parameters: Any = ...) -> Any: ...
    def executemany(self, sql: str, seq_of_parameters: Any = ...) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


@runtime_checkable
class DatabaseBackend(Protocol):
    """Protocol for database backends.

    Implementations must provide a context-manager connection() method
    that returns a ConnectionLike object.
    """

    @contextmanager
    def connection(self) -> Any:
        """Yield a database connection (context manager)."""
        ...

    def execute(self, sql: str, parameters: tuple = ()) -> list:
        """Execute a query and return all rows."""
        ...

    def execute_one(self, sql: str, parameters: tuple = ()) -> Any:
        """Execute a query and return one row or None."""
        ...

    def execute_write(self, sql: str, parameters: tuple = ()) -> int:
        """Execute a write query and return lastrowid or rowcount."""
        ...


class SQLiteBackend:
    """SQLite database backend (default, backward-compatible).

    Thread-safe via connection-per-call pattern (sqlite3 module handles this).
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    @contextmanager
    def connection(self):
        """Yield a sqlite3 connection as context manager."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, parameters: tuple = ()) -> list:
        """Execute a query and return all rows."""
        with self.connection() as conn:
            return conn.execute(sql, parameters).fetchall()

    def execute_one(self, sql: str, parameters: tuple = ()) -> Any:
        """Execute a query and return one row or None."""
        with self.connection() as conn:
            return conn.execute(sql, parameters).fetchone()

    def execute_write(self, sql: str, parameters: tuple = ()) -> int:
        """Execute a write query and return lastrowid."""
        with self.connection() as conn:
            cursor = conn.execute(sql, parameters)
            return cursor.lastrowid


# Registry of backend factories
_BACKEND_FACTORIES = {
    "sqlite": lambda db_path, **kwargs: SQLiteBackend(db_path),
}


def register_backend(name: str, factory):
    """Register a new database backend factory.

    Args:
        name: Backend name (e.g. "postgresql")
        factory: Callable(db_path, **kwargs) -> DatabaseBackend
    """
    _BACKEND_FACTORIES[name] = factory


def get_backend(db_path: str, backend_type: str = "sqlite", **kwargs) -> DatabaseBackend:
    """Get a database backend instance.

    Args:
        db_path: Path to database file (for SQLite) or connection URL
        backend_type: Backend type name (default: "sqlite")
        **kwargs: Additional backend-specific configuration

    Returns:
        Database backend instance

    Raises:
        ValueError: If backend_type is not registered
    """
    factory = _BACKEND_FACTORIES.get(backend_type)
    if factory is None:
        raise ValueError(
            f"Unknown database backend: {backend_type}. "
            f"Available: {list(_BACKEND_FACTORIES.keys())}"
        )
    return factory(db_path, **kwargs)
