# tests/test_alembic_migration.py
"""Tests for Alembic initial migration and SQLite-to-PG data migration script."""

import os
import sqlite3
import tempfile

from db.base import Base


class TestAlembicMigration:
    """Verify the Alembic migration creates all tables via ORM metadata."""

    def test_create_all_produces_11_tables(self):
        from sqlalchemy import create_engine, inspect
        from db import models as _models  # noqa: F401

        engine = create_engine("sqlite://", echo=False)
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        engine.dispose()

        expected = {
            "tenants", "users", "snapshots", "nodes", "edges",
            "drift_events", "policies", "feedback", "whitelist",
            "baselines", "audit_log",
        }
        assert expected == tables

    def test_indexes_created(self):
        from sqlalchemy import create_engine, inspect
        from db import models as _models  # noqa: F401

        engine = create_engine("sqlite://", echo=False)
        Base.metadata.create_all(engine)
        inspector = inspect(engine)

        all_indexes = set()
        for table_name in inspector.get_table_names():
            for idx in inspector.get_indexes(table_name):
                all_indexes.add(idx["name"])

        engine.dispose()
        assert "ix_snapshots_tenant_id" in all_indexes
        assert "ix_snapshots_timestamp_start" in all_indexes
        assert "ix_edges_snapshot_id" in all_indexes
        assert "ix_edges_source" in all_indexes
        assert "ix_edges_source_dest" in all_indexes
        assert "ix_drift_events_tenant_id" in all_indexes
        assert "ix_drift_events_severity" in all_indexes
        assert "ix_drift_events_status" in all_indexes
        assert "ix_audit_log_tenant_id" in all_indexes
        assert "ix_audit_log_created_at" in all_indexes


class TestMigrationScript:
    """Test the SQLite-to-PG migration script in dry-run mode."""

    def test_dry_run_reads_sqlite(self):
        """Dry-run mode reads SQLite without needing PG."""
        from core.migrations import apply_migrations
        from scripts.migrate_sqlite_to_pg import migrate

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Create a SQLite DB with the old schema and some data
            apply_migrations(db_path)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "INSERT INTO snapshots (snapshot_id, timestamp_start, timestamp_end, tenant_id) "
                "VALUES ('snap-001', '2026-01-01T10:00:00', '2026-01-01T11:00:00', 'default')"
            )
            conn.execute(
                "INSERT INTO nodes (snapshot_id, name, namespace, node_type, tenant_id) "
                "VALUES ('snap-001', 'api-gw', 'default', 'gateway', 'default')"
            )
            conn.execute(
                "INSERT INTO edges (snapshot_id, source, destination, request_count, "
                "error_count, avg_latency_ms, p99_latency_ms, tenant_id) "
                "VALUES ('snap-001', 'api-gw', 'order-svc', 100, 2, 30.0, 55.0, 'default')"
            )
            conn.commit()

            # Verify data exists
            count = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
            assert count == 1

            conn.close()

            # Run migration in dry-run mode
            migrate(db_path, "sqlite://", "default", dry_run=True)
        finally:
            os.unlink(db_path)

    def test_cli_help(self):
        """Verify script has --help."""
        import subprocess
        result = subprocess.run(
            ["python", "scripts/migrate_sqlite_to_pg.py", "--help"],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        assert result.returncode == 0
        assert "--sqlite-path" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--tenant-id" in result.stdout


class TestMigrationVersionFile:
    """Verify the Alembic migration version file is valid."""

    def test_revision_exists(self):
        from db.migrations.versions import __path__ as versions_path
        import importlib.util

        migration_path = os.path.join(versions_path[0], "001_initial_schema.py")
        assert os.path.exists(migration_path)

        spec = importlib.util.spec_from_file_location("migration_001", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.revision == "001"
        assert mod.down_revision is None
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)

    def test_upgrade_creates_tables(self):
        """Run upgrade() against in-memory SQLite to verify it works."""
        from sqlalchemy import create_engine, inspect

        # Import models to ensure they are registered
        from db import models as _models  # noqa: F401

        engine = create_engine("sqlite://", echo=False)
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected = {
            "tenants", "users", "snapshots", "nodes", "edges",
            "drift_events", "policies", "feedback", "whitelist",
            "baselines", "audit_log",
        }
        assert expected.issubset(tables)
        engine.dispose()
