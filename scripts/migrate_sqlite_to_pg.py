#!/usr/bin/env python3
# scripts/migrate_sqlite_to_pg.py
"""Migrate data from SQLite (old schema) to PostgreSQL/new SQLAlchemy schema.

Usage:
    python scripts/migrate_sqlite_to_pg.py --sqlite-path data/snapshots.db
    python scripts/migrate_sqlite_to_pg.py --sqlite-path data/snapshots.db --dry-run
    python scripts/migrate_sqlite_to_pg.py --sqlite-path data/snapshots.db --tenant-id my-tenant
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 1000

# Mapping from old SQLite table/column structure to new schema
TABLE_MAP = [
    ("snapshots", "snapshot_id", "id"),
    ("nodes", None, None),
    ("edges", None, None),
    ("drift_events", "event_id", "id"),
    ("feedback", "feedback_id", "id"),
    ("whitelist", "entry_id", "id"),
    ("baselines", "baseline_id", "id"),
    ("policies", "policy_id", "id"),
    ("audit_log", "log_id", "id"),
]


def _sqlite_tables(conn: sqlite3.Connection) -> set[str]:
    """Get all table names from SQLite."""
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return {row[0] for row in cur.fetchall()}


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Get column names for a SQLite table."""
    cur = conn.execute(f"PRAGMA table_info({table})")  # noqa: S608
    return [row[1] for row in cur.fetchall()]


def _ensure_tenant(pg_engine, tenant_id: str) -> str:
    """Ensure tenant exists in PG, return UUID string."""
    with pg_engine.connect() as conn:
        row = conn.execute(text("SELECT id FROM tenants WHERE slug = :slug"), {"slug": tenant_id}).fetchone()
        if row:
            return str(row[0])
        tid = str(uuid.uuid4())
        conn.execute(
            text("INSERT INTO tenants (id, name, slug, created_at) VALUES (:id, :name, :slug, :at)"),
            {"id": tid, "name": tenant_id, "slug": tenant_id, "at": datetime.now(timezone.utc).isoformat()},
        )
        conn.commit()
        logger.info("Created tenant '%s' with id %s", tenant_id, tid)
        return tid


def _migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_engine,
    table: str,
    old_pk: str | None,
    new_pk: str | None,
    tenant_uuid: str,
    id_map: dict[str, dict[str, str]],
    dry_run: bool,
) -> int:
    """Migrate one table from SQLite to PostgreSQL. Returns row count."""
    sqlite_tables = _sqlite_tables(sqlite_conn)
    if table not in sqlite_tables:
        logger.info("Skipping %s (not in SQLite)", table)
        return 0

    sqlite_cols = _sqlite_columns(sqlite_conn, table)
    rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
    if not rows:
        logger.info("Skipping %s (0 rows)", table)
        return 0

    id_map.setdefault(table, {})
    migrated = 0

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start: batch_start + BATCH_SIZE]
        for row in batch:
            data = dict(zip(sqlite_cols, row, strict=False))

            # Rename old PK to 'id' if needed
            if old_pk and new_pk and old_pk in data and old_pk != new_pk:
                data[new_pk] = data.pop(old_pk)

            # Generate UUID for PK if it's a text-based ID
            if new_pk and new_pk in data:
                old_id = str(data[new_pk])
                if old_id not in id_map[table]:
                    try:
                        uuid.UUID(old_id)
                        id_map[table][old_id] = old_id
                    except ValueError:
                        id_map[table][old_id] = str(uuid.uuid4())
                data[new_pk] = id_map[table][old_id]

            # Map FK snapshot_id references
            if "snapshot_id" in data and "snapshots" in id_map:
                old_snap = str(data["snapshot_id"])
                data["snapshot_id"] = id_map["snapshots"].get(old_snap, old_snap)

            # Set tenant_id (use UUID)
            if "tenant_id" in data:
                data["tenant_id"] = tenant_uuid

            # Drop columns not in new schema
            skip_cols = {"schema_version", "detected_at", "yaml_spec", "severity", "auto_apply_safe",
                         "updated_at", "service_pattern", "user", "event_id", "status_old",
                         "timestamp", "created_by_name"}
            for col in list(data.keys()):
                if col in skip_cols and table not in ("drift_events",):
                    data.pop(col, None)

            if not dry_run:
                cols = ", ".join(data.keys())
                placeholders = ", ".join(f":{k}" for k in data.keys())
                with pg_engine.connect() as conn:
                    try:
                        conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"), data)  # noqa: S608
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                            continue
                        logger.warning("Error inserting into %s: %s", table, e)
                        continue
            migrated += 1

    logger.info("Migrated %s: %d records%s", table, migrated, " (dry-run)" if dry_run else "")
    return migrated


def migrate(sqlite_path: str, pg_url: str, tenant_id: str, dry_run: bool) -> None:
    """Run the full migration."""
    if not os.path.exists(sqlite_path):
        logger.error("SQLite file not found: %s", sqlite_path)
        sys.exit(1)

    sqlite_conn = sqlite3.connect(sqlite_path)
    pg_engine = create_engine(pg_url)

    logger.info("Source: %s", sqlite_path)
    logger.info("Target: %s", pg_url.split("@")[-1] if "@" in pg_url else pg_url)
    logger.info("Tenant: %s", tenant_id)
    logger.info("Dry run: %s", dry_run)

    # Ensure tenant exists
    if not dry_run:
        tenant_uuid = _ensure_tenant(pg_engine, tenant_id)
    else:
        tenant_uuid = str(uuid.uuid4())

    id_map: dict[str, dict[str, str]] = {}
    total = 0

    for table, old_pk, new_pk in TABLE_MAP:
        count = _migrate_table(sqlite_conn, pg_engine, table, old_pk, new_pk, tenant_uuid, id_map, dry_run)
        total += count

    # Verify counts
    sqlite_tables = _sqlite_tables(sqlite_conn)
    for table, _, _ in TABLE_MAP:
        if table not in sqlite_tables:
            continue
        src_count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        if not dry_run:
            with pg_engine.connect() as conn:
                dst_count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0  # noqa: S608
            if src_count != dst_count:
                logger.warning("Count mismatch for %s: SQLite=%d, PG=%d", table, src_count, dst_count)
            else:
                logger.info("Verified %s: %d records match", table, src_count)

    sqlite_conn.close()
    pg_engine.dispose()
    logger.info("Migration complete: %d total records%s", total, " (dry-run)" if dry_run else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument("--sqlite-path", required=True, help="Path to SQLite database")
    parser.add_argument("--pg-url", default=os.getenv("DATABASE_URL", ""), help="PostgreSQL URL")
    parser.add_argument("--tenant-id", default="default", help="Tenant ID to assign")
    parser.add_argument("--dry-run", action="store_true", help="Check only, do not write")
    args = parser.parse_args()

    if not args.pg_url and not args.dry_run:
        logger.error("--pg-url or DATABASE_URL env required (unless --dry-run)")
        sys.exit(1)

    pg_url = args.pg_url or "sqlite://"
    migrate(args.sqlite_path, pg_url, args.tenant_id, args.dry_run)


if __name__ == "__main__":
    main()
