# db/adapter.py
"""Adapter: wraps async SnapshotRepository behind the old sync SnapshotStore interface.

Temporary bridge — allows existing sync code (drift detector, scorer, API) to
work unchanged while the data layer moves to async SQLAlchemy ORM.

Usage:
    from db.adapter import StorageAdapter
    store = StorageAdapter(session_factory)
    store.save_snapshot(old_snapshot, tenant_id="default")
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from graph.models import Edge as OldEdge
from graph.models import Node as OldNode
from graph.models import Snapshot as OldSnapshot

# Namespace UUID for deterministic id mapping (old string id → UUID)
_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _to_uuid(value: str) -> uuid.UUID:
    """Convert an arbitrary string to a deterministic UUID via uuid5."""
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return uuid.uuid5(_NS, value)


def _run_async(coro):
    """Run a coroutine from synchronous code (safe even without running loop)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class StorageAdapter:
    """Sync wrapper around async SnapshotRepository for backward compatibility.

    Matches the graph.storage.SnapshotStore interface so existing code
    continues to work unchanged during the async migration.
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    # -- public interface (mirrors SnapshotStore) ---------------------------

    def save_snapshot(self, snapshot: OldSnapshot, *, tenant_id=...) -> None:
        if tenant_id is ... or tenant_id is None:
            raise ValueError("tenant_id required for save operations")
        _run_async(self._save(snapshot, tenant_id))

    def load_snapshot(self, snapshot_id: str, *, tenant_id=...) -> OldSnapshot | None:
        if tenant_id is ...:
            raise ValueError("tenant_id required")
        return _run_async(self._load(snapshot_id, tenant_id))

    def list_snapshots(self, *, tenant_id=...) -> list[dict]:
        if tenant_id is ...:
            raise ValueError("tenant_id required")
        return _run_async(self._list(tenant_id))

    def get_latest_two(self, *, tenant_id=...) -> tuple[OldSnapshot, OldSnapshot] | None:
        if tenant_id is ...:
            raise ValueError("tenant_id required")
        return _run_async(self._latest_two(tenant_id))

    def delete_snapshot(self, snapshot_id: str, *, tenant_id=...) -> bool:
        if tenant_id is ... or tenant_id is None:
            raise ValueError("tenant_id required for delete operations")
        return _run_async(self._delete(snapshot_id, tenant_id))

    # -- async implementations ---------------------------------------------

    async def _save(self, snapshot: OldSnapshot, tenant_id: str) -> None:
        from db.repository import SnapshotRepository

        snap_uuid = str(_to_uuid(snapshot.snapshot_id))
        data = {
            "id": snap_uuid,
            "timestamp_start": snapshot.timestamp_start,
            "timestamp_end": snapshot.timestamp_end,
            "metadata_": {"original_id": snapshot.snapshot_id},
            "nodes": [{"name": n.name, "namespace": n.namespace, "node_type": n.node_type} for n in snapshot.nodes],
            "edges": [
                {"source": e.source, "destination": e.destination, "request_count": e.request_count,
                 "error_count": e.error_count, "error_rate": e.error_rate(),
                 "avg_latency_ms": e.avg_latency_ms, "p99_latency_ms": e.p99_latency_ms}
                for e in snapshot.edges
            ],
        }
        async with self._session_factory() as session:
            repo = SnapshotRepository(session)
            await repo.save(data, tenant_id)
            await session.commit()

    async def _load(self, snapshot_id: str, tenant_id: str | None) -> OldSnapshot | None:
        from db.repository import SnapshotRepository

        async with self._session_factory() as session:
            repo = SnapshotRepository(session)
            if tenant_id is None:
                return None
            d = await repo.get(str(_to_uuid(snapshot_id)), tenant_id)
        if d is None:
            return None
        return self._dict_to_snapshot(d)

    async def _list(self, tenant_id: str | None) -> list[dict]:
        from db.repository import SnapshotRepository

        if tenant_id is None:
            return []
        async with self._session_factory() as session:
            repo = SnapshotRepository(session)
            items = await repo.list_all(tenant_id)
        result = []
        for it in items:
            meta = it.get("metadata_") or {}
            sid = meta.get("original_id", it["id"])
            result.append({"snapshot_id": sid, "timestamp_start": it["timestamp_start"],
                           "timestamp_end": it["timestamp_end"]})
        return result

    async def _latest_two(self, tenant_id: str | None) -> tuple[OldSnapshot, OldSnapshot] | None:
        from db.repository import SnapshotRepository

        if tenant_id is None:
            return None
        async with self._session_factory() as session:
            repo = SnapshotRepository(session)
            items = await repo.list_all(tenant_id, limit=2)
        if len(items) < 2:
            return None
        # list_all returns most recent first
        async with self._session_factory() as session:
            repo = SnapshotRepository(session)
            latest_d = await repo.get(items[0]["id"], tenant_id)
            previous_d = await repo.get(items[1]["id"], tenant_id)
        if latest_d is None or previous_d is None:
            return None
        return (self._dict_to_snapshot(previous_d), self._dict_to_snapshot(latest_d))

    async def _delete(self, snapshot_id: str, tenant_id: str) -> bool:
        from sqlalchemy import delete as sa_delete
        from db.models import Snapshot

        snap_uuid = _to_uuid(snapshot_id)
        async with self._session_factory() as session:
            stmt = sa_delete(Snapshot).where(
                Snapshot.id == snap_uuid,
                Snapshot.tenant_id == _to_uuid(tenant_id),
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    # -- conversion helpers -------------------------------------------------

    @staticmethod
    def _dict_to_snapshot(d: dict) -> OldSnapshot:
        """Convert repo dict back to old graph.models.Snapshot dataclass."""
        nodes = [OldNode(name=n["name"], namespace=n.get("namespace", "default"),
                         node_type=n.get("node_type", "service")) for n in d.get("nodes", [])]
        edges = [OldEdge(source=e["source"], destination=e["destination"],
                         request_count=e.get("request_count", 0), error_count=e.get("error_count", 0),
                         avg_latency_ms=e.get("avg_latency_ms", 0.0), p99_latency_ms=e.get("p99_latency_ms", 0.0))
                 for e in d.get("edges", [])]
        ts_start = d["timestamp_start"]
        ts_end = d["timestamp_end"]
        if isinstance(ts_start, str):
            ts_start = datetime.fromisoformat(ts_start)
        if isinstance(ts_end, str):
            ts_end = datetime.fromisoformat(ts_end)
        # Recover original string ID from metadata if stored by adapter
        meta = d.get("metadata_") or {}
        snap_id = meta.get("original_id", d["id"])
        return OldSnapshot(snapshot_id=snap_id, timestamp_start=ts_start,
                           timestamp_end=ts_end, nodes=nodes, edges=edges)
