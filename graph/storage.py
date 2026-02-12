# graph/storage.py
# SQLite хранилище для снапшотов

import os
import sqlite3
from datetime import datetime

from graph.models import Node, Edge, Snapshot
from core.migrations import apply_migrations


class SnapshotStore:
    """SQLite хранилище снапшотов графа."""

    def __init__(self, db_path: str = "data/snapshots.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database using migration system."""
        apply_migrations(self.db_path)

    @staticmethod
    def _require_tenant(tenant_id):
        """Validate tenant_id is provided (None = super_admin sees all)."""
        if tenant_id is ...:
            raise ValueError("tenant_id required")

    # ------------------------------------------------------------------
    def save_snapshot(self, snapshot: Snapshot, *, tenant_id=...) -> None:
        """Сохраняет снапшот (snapshot + edges + nodes) в БД."""
        self._require_tenant(tenant_id)
        if tenant_id is None:
            raise ValueError("tenant_id required for save operations")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO snapshots (snapshot_id, timestamp_start, timestamp_end, tenant_id) "
                "VALUES (?, ?, ?, ?)",
                (
                    snapshot.snapshot_id,
                    snapshot.timestamp_start.isoformat(),
                    snapshot.timestamp_end.isoformat(),
                    tenant_id,
                ),
            )
            # Удаляем старые данные при перезаписи
            conn.execute("DELETE FROM edges WHERE snapshot_id = ?", (snapshot.snapshot_id,))
            conn.execute("DELETE FROM nodes WHERE snapshot_id = ?", (snapshot.snapshot_id,))

            conn.executemany(
                "INSERT INTO edges (snapshot_id, source, destination, request_count, "
                "error_count, avg_latency_ms, p99_latency_ms, tenant_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        snapshot.snapshot_id,
                        e.source,
                        e.destination,
                        e.request_count,
                        e.error_count,
                        e.avg_latency_ms,
                        e.p99_latency_ms,
                        tenant_id,
                    )
                    for e in snapshot.edges
                ],
            )
            conn.executemany(
                "INSERT INTO nodes (snapshot_id, name, namespace, node_type, tenant_id) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (snapshot.snapshot_id, n.name, n.namespace, n.node_type, tenant_id)
                    for n in snapshot.nodes
                ],
            )

    # ------------------------------------------------------------------
    def load_snapshot(self, snapshot_id: str, *, tenant_id=...) -> Snapshot | None:
        """Загружает снапшот по ID. Возвращает None если не найден."""
        self._require_tenant(tenant_id)
        with sqlite3.connect(self.db_path) as conn:
            if tenant_id is None:
                row = conn.execute(
                    "SELECT snapshot_id, timestamp_start, timestamp_end "
                    "FROM snapshots WHERE snapshot_id = ?",
                    (snapshot_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT snapshot_id, timestamp_start, timestamp_end "
                    "FROM snapshots WHERE snapshot_id = ? AND tenant_id = ?",
                    (snapshot_id, tenant_id),
                ).fetchone()
            if row is None:
                return None

            edges = [
                Edge(
                    source=r[0],
                    destination=r[1],
                    request_count=r[2],
                    error_count=r[3],
                    avg_latency_ms=r[4],
                    p99_latency_ms=r[5],
                )
                for r in conn.execute(
                    "SELECT source, destination, request_count, error_count, "
                    "avg_latency_ms, p99_latency_ms FROM edges WHERE snapshot_id = ?",
                    (snapshot_id,),
                ).fetchall()
            ]

            nodes = [
                Node(name=r[0], namespace=r[1], node_type=r[2])
                for r in conn.execute(
                    "SELECT name, namespace, node_type FROM nodes WHERE snapshot_id = ?",
                    (snapshot_id,),
                ).fetchall()
            ]

        return Snapshot(
            snapshot_id=row[0],
            timestamp_start=datetime.fromisoformat(row[1]),
            timestamp_end=datetime.fromisoformat(row[2]),
            edges=edges,
            nodes=nodes,
        )

    # ------------------------------------------------------------------
    def list_snapshots(self, *, tenant_id=...) -> list[dict]:
        """Возвращает список снапшотов [{snapshot_id, timestamp_start, timestamp_end}]."""
        self._require_tenant(tenant_id)
        with sqlite3.connect(self.db_path) as conn:
            if tenant_id is None:
                rows = conn.execute(
                    "SELECT snapshot_id, timestamp_start, timestamp_end "
                    "FROM snapshots ORDER BY timestamp_start"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT snapshot_id, timestamp_start, timestamp_end "
                    "FROM snapshots WHERE tenant_id = ? ORDER BY timestamp_start",
                    (tenant_id,),
                ).fetchall()
        return [
            {
                "snapshot_id": r[0],
                "timestamp_start": r[1],
                "timestamp_end": r[2],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    def get_latest_two(self, *, tenant_id=...) -> tuple[Snapshot, Snapshot] | None:
        """Возвращает два последних снапшота (previous, latest) для drift-сравнения.

        Возвращает None если в БД меньше двух снапшотов.
        """
        self._require_tenant(tenant_id)
        with sqlite3.connect(self.db_path) as conn:
            if tenant_id is None:
                rows = conn.execute(
                    "SELECT snapshot_id FROM snapshots "
                    "ORDER BY timestamp_start DESC LIMIT 2"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT snapshot_id FROM snapshots "
                    "WHERE tenant_id = ? ORDER BY timestamp_start DESC LIMIT 2",
                    (tenant_id,),
                ).fetchall()

        if len(rows) < 2:
            return None

        latest = self.load_snapshot(rows[0][0], tenant_id=tenant_id)
        previous = self.load_snapshot(rows[1][0], tenant_id=tenant_id)

        if latest is None or previous is None:
            return None

        return (previous, latest)

    def delete_snapshot(self, snapshot_id: str, *, tenant_id=...) -> bool:
        """Удаляет снапшот из базы данных.

        Args:
            snapshot_id: ID снапшота для удаления
            tenant_id: tenant identifier

        Returns:
            True если удален, False если не найден
        """
        self._require_tenant(tenant_id)
        if tenant_id is None:
            raise ValueError("tenant_id required for delete operations")
        with sqlite3.connect(self.db_path) as conn:
            # Удаляем edges
            conn.execute("DELETE FROM edges WHERE snapshot_id = ?", (snapshot_id,))
            # Удаляем nodes
            conn.execute("DELETE FROM nodes WHERE snapshot_id = ?", (snapshot_id,))
            # Удаляем snapshot
            cursor = conn.execute(
                "DELETE FROM snapshots WHERE snapshot_id = ? AND tenant_id = ?",
                (snapshot_id, tenant_id),
            )
            conn.commit()
            return cursor.rowcount > 0


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    store = SnapshotStore()
    snapshots = store.list_snapshots(tenant_id=None)
    print(f"SnapshotStore: {store.db_path}")
    print("  Tables created: OK")
    print(f"  Snapshots in DB: {len(snapshots)}")
    for s in snapshots:
        print(f"    {s['snapshot_id'][:12]}... {s['timestamp_start']} → {s['timestamp_end']}")
