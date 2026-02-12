# tests/test_database_backend.py
"""Tests for core.database — Database abstraction layer."""

import sqlite3
import pytest

from core.database import SQLiteBackend, get_backend, register_backend


@pytest.fixture
def sqlite_backend(tmp_path):
    """Create a SQLiteBackend with a temp database."""
    db_path = str(tmp_path / "test.db")
    backend = SQLiteBackend(db_path)
    with backend.connection() as conn:
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    return backend


class TestSQLiteBackend:
    """Tests for SQLiteBackend implementation."""

    def test_connection_context_manager(self, sqlite_backend):
        """connection() yields a working connection."""
        with sqlite_backend.connection() as conn:
            conn.execute("INSERT INTO items (name) VALUES (?)", ("test",))
        # Verify committed
        rows = sqlite_backend.execute("SELECT name FROM items")
        assert rows == [("test",)]

    def test_connection_rollback_on_error(self, sqlite_backend):
        """connection() rolls back on exception."""
        with pytest.raises(sqlite3.OperationalError):
            with sqlite_backend.connection() as conn:
                conn.execute("INSERT INTO items (name) VALUES (?)", ("will_rollback",))
                conn.execute("INVALID SQL")
        # Row should not be committed
        rows = sqlite_backend.execute("SELECT name FROM items")
        assert rows == []

    def test_execute(self, sqlite_backend):
        """execute() returns all rows."""
        with sqlite_backend.connection() as conn:
            conn.execute("INSERT INTO items (name) VALUES (?)", ("a",))
            conn.execute("INSERT INTO items (name) VALUES (?)", ("b",))
        rows = sqlite_backend.execute("SELECT name FROM items ORDER BY name")
        assert rows == [("a",), ("b",)]

    def test_execute_one(self, sqlite_backend):
        """execute_one() returns single row or None."""
        assert sqlite_backend.execute_one("SELECT name FROM items") is None
        with sqlite_backend.connection() as conn:
            conn.execute("INSERT INTO items (name) VALUES (?)", ("single",))
        row = sqlite_backend.execute_one("SELECT name FROM items WHERE name = ?", ("single",))
        assert row == ("single",)

    def test_execute_write(self, sqlite_backend):
        """execute_write() returns lastrowid."""
        row_id = sqlite_backend.execute_write(
            "INSERT INTO items (name) VALUES (?)", ("written",)
        )
        assert row_id is not None
        assert row_id > 0

    def test_creates_directory(self, tmp_path):
        """Backend creates parent directories if needed."""
        db_path = str(tmp_path / "subdir" / "nested" / "test.db")
        backend = SQLiteBackend(db_path)
        with backend.connection() as conn:
            conn.execute("CREATE TABLE t (id INTEGER)")
        assert (tmp_path / "subdir" / "nested" / "test.db").exists()


class TestGetBackend:
    """Tests for get_backend() factory."""

    def test_get_sqlite_backend(self, tmp_path):
        """get_backend() returns SQLiteBackend for 'sqlite' type."""
        db_path = str(tmp_path / "factory.db")
        backend = get_backend(db_path, backend_type="sqlite")
        assert isinstance(backend, SQLiteBackend)

    def test_get_unknown_backend_raises(self, tmp_path):
        """get_backend() raises ValueError for unknown backend."""
        with pytest.raises(ValueError, match="Unknown database backend"):
            get_backend(str(tmp_path / "x.db"), backend_type="unknown")

    def test_register_custom_backend(self, tmp_path):
        """register_backend() allows adding new backends."""

        class MockBackend:
            def __init__(self, db_path):
                self.db_path = db_path

        register_backend("mock", lambda db_path, **kw: MockBackend(db_path))
        backend = get_backend(str(tmp_path / "mock.db"), backend_type="mock")
        assert isinstance(backend, MockBackend)

    def test_default_backend_is_sqlite(self, tmp_path):
        """get_backend() defaults to sqlite."""
        db_path = str(tmp_path / "default.db")
        backend = get_backend(db_path)
        assert isinstance(backend, SQLiteBackend)
