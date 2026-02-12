# graph/storage.py
# SQLite хранилище для снапшотов

import os
import sqlite3
from datetime import datetime

from graph.models import Node, Edge, Snapshot


class SnapshotStore:
    """SQLite хранилище снапшотов графа."""

    def __init__(self, db_path: str = "data/snapshots.db"):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
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

    # ------------------------------------------------------------------
    def save_snapshot(self, snapshot: Snapshot) -> None:
        """Сохраняет снапшот (snapshot + edges + nodes) в БД."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO snapshots (snapshot_id, timestamp_start, timestamp_end) "
                "VALUES (?, ?, ?)",
                (
                    snapshot.snapshot_id,
                    snapshot.timestamp_start.isoformat(),
                    snapshot.timestamp_end.isoformat(),
                ),
            )
            # Удаляем старые данные при перезаписи
            conn.execute("DELETE FROM edges WHERE snapshot_id = ?", (snapshot.snapshot_id,))
            conn.execute("DELETE FROM nodes WHERE snapshot_id = ?", (snapshot.snapshot_id,))

            conn.executemany(
                "INSERT INTO edges (snapshot_id, source, destination, request_count, "
                "error_count, avg_latency_ms, p99_latency_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        snapshot.snapshot_id,
                        e.source,
                        e.destination,
                        e.request_count,
                        e.error_count,
                        e.avg_latency_ms,
                        e.p99_latency_ms,
                    )
                    for e in snapshot.edges
                ],
            )
            conn.executemany(
                "INSERT INTO nodes (snapshot_id, name, namespace, node_type) "
                "VALUES (?, ?, ?, ?)",
                [
                    (snapshot.snapshot_id, n.name, n.namespace, n.node_type)
                    for n in snapshot.nodes
                ],
            )

    # ------------------------------------------------------------------
    def load_snapshot(self, snapshot_id: str) -> Snapshot | None:
        """Загружает снапшот по ID. Возвращает None если не найден."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT snapshot_id, timestamp_start, timestamp_end "
                "FROM snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
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
    def list_snapshots(self) -> list[dict]:
        """Возвращает список снапшотов [{snapshot_id, timestamp_start, timestamp_end}]."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT snapshot_id, timestamp_start, timestamp_end "
                "FROM snapshots ORDER BY timestamp_start"
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
    def get_latest_two(self) -> tuple[Snapshot, Snapshot] | None:
        """Возвращает два последних снапшота (previous, latest) для drift-сравнения.

        Возвращает None если в БД меньше двух снапшотов.
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT snapshot_id FROM snapshots "
                "ORDER BY timestamp_start DESC LIMIT 2"
            ).fetchall()

        if len(rows) < 2:
            return None

        latest = self.load_snapshot(rows[0][0])
        previous = self.load_snapshot(rows[1][0])

        if latest is None or previous is None:
            return None

        return (previous, latest)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Удаляет снапшот из базы данных.

        Args:
            snapshot_id: ID снапшота для удаления

        Returns:
            True если удален, False если не найден
        """
        with sqlite3.connect(self.db_path) as conn:
            # Удаляем edges
            conn.execute("DELETE FROM edges WHERE snapshot_id = ?", (snapshot_id,))
            # Удаляем nodes
            conn.execute("DELETE FROM nodes WHERE snapshot_id = ?", (snapshot_id,))
            # Удаляем snapshot
            cursor = conn.execute("DELETE FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
            conn.commit()
            return cursor.rowcount > 0


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    store = SnapshotStore()
    snapshots = store.list_snapshots()
    print(f"SnapshotStore: {store.db_path}")
    print("  Tables created: OK")
    print(f"  Snapshots in DB: {len(snapshots)}")
    for s in snapshots:
        print(f"    {s['snapshot_id'][:12]}... {s['timestamp_start']} → {s['timestamp_end']}")
