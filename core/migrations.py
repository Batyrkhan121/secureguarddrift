# core/migrations.py
"""Database migration system for SecureGuard Drift."""

import os
import sqlite3
import shutil
import logging
from datetime import datetime, timezone
from typing import Callable

logger = logging.getLogger(__name__)


def migration_v1(conn: sqlite3.Connection) -> None:
    """v1: Base schema — snapshots, nodes, edges."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            snapshot_id    TEXT PRIMARY KEY,
            timestamp_start TEXT NOT NULL,
            timestamp_end   TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id     TEXT NOT NULL REFERENCES snapshots(snapshot_id),
            source          TEXT NOT NULL,
            destination     TEXT NOT NULL,
            request_count   INTEGER NOT NULL,
            error_count     INTEGER NOT NULL,
            avg_latency_ms  REAL NOT NULL,
            p99_latency_ms  REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
            name        TEXT NOT NULL,
            namespace   TEXT NOT NULL,
            node_type   TEXT NOT NULL
        )
    """)


def migration_v2(conn: sqlite3.Connection) -> None:
    """v2: Add tenant_id to all tables for multi-tenancy."""
    # Check if column exists before adding (SQLite doesn't have IF NOT EXISTS for ALTER)
    cursor = conn.execute("PRAGMA table_info(snapshots)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'tenant_id' not in columns:
        conn.execute("ALTER TABLE snapshots ADD COLUMN tenant_id TEXT DEFAULT 'default'")
    
    cursor = conn.execute("PRAGMA table_info(edges)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'tenant_id' not in columns:
        conn.execute("ALTER TABLE edges ADD COLUMN tenant_id TEXT DEFAULT 'default'")
    
    cursor = conn.execute("PRAGMA table_info(nodes)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'tenant_id' not in columns:
        conn.execute("ALTER TABLE nodes ADD COLUMN tenant_id TEXT DEFAULT 'default'")
    
    # Create indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_tenant ON snapshots(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_tenant ON edges(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_tenant ON nodes(tenant_id)")


def migration_v3(conn: sqlite3.Connection) -> None:
    """v3: Add feedback table for ML feedback loop."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            event_type TEXT NOT NULL,
            verdict TEXT NOT NULL,
            comment TEXT,
            user TEXT,
            created_at TIMESTAMP NOT NULL,
            tenant_id TEXT DEFAULT 'default'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_edge ON feedback(source, destination)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_verdict ON feedback(verdict)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON feedback(tenant_id)")


def migration_v4(conn: sqlite3.Connection) -> None:
    """v4: Add whitelist and suppress_rules tables."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_by TEXT,
            created_at TIMESTAMP NOT NULL,
            tenant_id TEXT DEFAULT 'default',
            UNIQUE(source, destination, tenant_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS suppress_rules (
            rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            service_pattern TEXT NOT NULL,
            reason TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_by TEXT,
            created_at TIMESTAMP NOT NULL,
            tenant_id TEXT DEFAULT 'default'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_whitelist_tenant ON whitelist(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_suppress_tenant ON suppress_rules(tenant_id)")


def migration_v5(conn: sqlite3.Connection) -> None:
    """v5: Add drift_events table for persistent storage."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drift_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            severity TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            detected_at TIMESTAMP NOT NULL,
            snapshot_id TEXT NOT NULL,
            tenant_id TEXT DEFAULT 'default'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_severity ON drift_events(severity)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant ON drift_events(tenant_id)")


def migration_v6(conn: sqlite3.Connection) -> None:
    """v6: Add policies table for NetworkPolicy suggestions."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            policy_id       TEXT PRIMARY KEY,
            yaml_spec       TEXT NOT NULL,
            reason          TEXT NOT NULL,
            risk_score      INTEGER NOT NULL,
            severity        TEXT NOT NULL,
            source          TEXT NOT NULL,
            destination     TEXT NOT NULL,
            auto_apply_safe INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            created_at      TEXT NOT NULL,
            updated_at      TEXT,
            tenant_id       TEXT DEFAULT 'default'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_policies_status ON policies(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_policies_severity ON policies(severity)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_policies_tenant ON policies(tenant_id)")


def migration_v7(conn: sqlite3.Connection) -> None:
    """v7: Add baselines table for ML anomaly detection."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS baselines (
            baseline_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            mean_request_count REAL NOT NULL,
            std_request_count REAL NOT NULL,
            mean_error_rate REAL NOT NULL,
            std_error_rate REAL NOT NULL,
            mean_p99_latency REAL NOT NULL,
            std_p99_latency REAL NOT NULL,
            last_updated TIMESTAMP NOT NULL,
            tenant_id TEXT DEFAULT 'default',
            UNIQUE(source, destination, tenant_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_baselines_edge ON baselines(source, destination)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_baselines_tenant ON baselines(tenant_id)")


def migration_v8(conn: sqlite3.Connection) -> None:
    """v8: Add audit_log table for security tracking."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT,
            status TEXT NOT NULL,
            details TEXT,
            tenant_id TEXT DEFAULT 'default'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_log(tenant_id)")


# Migration registry: (version, description, function)
MIGRATIONS: list[tuple[int, str, Callable]] = [
    (1, "Base schema", migration_v1),
    (2, "Add tenant_id", migration_v2),
    (3, "Add feedback table", migration_v3),
    (4, "Add whitelist table", migration_v4),
    (5, "Add drift_events table", migration_v5),
    (6, "Add policies table", migration_v6),
    (7, "Add baselines table", migration_v7),
    (8, "Add audit_log table", migration_v8),
]


def get_version(db_path: str) -> int:
    """Get current schema version from database.
    
    Returns:
        Current version (0 if no versioning table exists)
    """
    if not os.path.exists(db_path):
        return 0
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0
    except sqlite3.OperationalError:
        # Table doesn't exist
        return 0


def apply_migrations(db_path: str) -> None:
    """Apply all pending migrations to database.
    
    Args:
        db_path: Path to SQLite database file
    """
    # Create directory if needed
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    # Create database connection
    conn = sqlite3.connect(db_path)
    
    try:
        # Create schema_version table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL,
                description TEXT
            )
        """)
        conn.commit()
        
        # Get current version
        current_version = get_version(db_path)
        logger.info(f"Current database version: {current_version}")
        
        # Apply pending migrations
        for version, description, migration_func in MIGRATIONS:
            if version > current_version:
                logger.info(f"Applying migration v{version}: {description}...")
                
                # Backup database before migration
                if os.path.exists(db_path):
                    backup_path = f"{db_path}.v{version-1}.bak"
                    shutil.copy2(db_path, backup_path)
                    logger.info(f"Created backup: {backup_path}")
                
                try:
                    # Apply migration in transaction
                    migration_func(conn)
                    
                    # Record migration
                    conn.execute(
                        "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                        (version, datetime.now(timezone.utc).isoformat(), description)
                    )
                    conn.commit()
                    logger.info(f"Migration v{version} applied successfully")
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Migration v{version} failed: {e}")
                    raise
        
        final_version = get_version(db_path)
        logger.info(f"Database at version {final_version}")
        
    finally:
        conn.close()


if __name__ == "__main__":
    # Test migrations
    import tempfile
    logging.basicConfig(level=logging.INFO)
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db = f.name
    
    print(f"Testing migrations on {test_db}")
    apply_migrations(test_db)
    version = get_version(test_db)
    print(f"Final version: {version}")
    
    # Cleanup
    os.unlink(test_db)
    print("Test completed successfully")
