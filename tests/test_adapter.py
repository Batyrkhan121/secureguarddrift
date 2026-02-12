# tests/test_adapter.py
"""Tests for db.adapter — StorageAdapter backward compatibility layer."""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.adapter import StorageAdapter
from db.base import Base
from db.models import Tenant
from graph.models import Edge, Node, Snapshot


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_adapter():
    """Create an in-memory adapter with a tenant. Returns (adapter, tenant_id, engine)."""

    async def _setup():
        engine = create_async_engine("sqlite+aiosqlite://", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            tenant = Tenant(name="Test", slug="test")
            session.add(tenant)
            await session.commit()
            tid = str(tenant.id)
        return StorageAdapter(factory), tid, engine

    return _run(_setup())


class TestStorageAdapterSaveAndLoad:
    """Verify save_snapshot + load_snapshot round-trip."""

    def test_save_and_load_round_trip(self):
        adapter, tid, engine = _make_adapter()
        nodes = [Node(name="svc-a", namespace="prod", node_type="service")]
        edges = [Edge(source="svc-a", destination="svc-b",
                      request_count=100, error_count=5,
                      avg_latency_ms=25.5, p99_latency_ms=50.3)]
        original = Snapshot(
            snapshot_id="test-001",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=nodes, edges=edges,
        )
        adapter.save_snapshot(original, tenant_id=tid)
        loaded = adapter.load_snapshot("test-001", tenant_id=tid)

        assert loaded is not None
        assert loaded.snapshot_id == "test-001"
        assert len(loaded.nodes) == 1
        assert loaded.nodes[0].name == "svc-a"
        assert len(loaded.edges) == 1
        assert loaded.edges[0].source == "svc-a"
        assert loaded.edges[0].request_count == 100
        _run(engine.dispose())

    def test_load_nonexistent_returns_none(self):
        adapter, tid, engine = _make_adapter()
        result = adapter.load_snapshot("no-such-id", tenant_id=tid)
        assert result is None
        _run(engine.dispose())


class TestStorageAdapterList:
    """Verify list_snapshots returns correct format."""

    def test_list_snapshots(self):
        adapter, tid, engine = _make_adapter()
        adapter.save_snapshot(Snapshot(
            snapshot_id="s1",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a")], edges=[],
        ), tenant_id=tid)
        adapter.save_snapshot(Snapshot(
            snapshot_id="s2",
            timestamp_start=datetime(2026, 1, 2, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 2, 11, 0, 0),
            nodes=[Node(name="b")], edges=[],
        ), tenant_id=tid)

        result = adapter.list_snapshots(tenant_id=tid)
        assert len(result) == 2
        assert "snapshot_id" in result[0]
        assert "timestamp_start" in result[0]
        _run(engine.dispose())


class TestStorageAdapterLatestTwo:
    """Verify get_latest_two returns correct pair."""

    def test_returns_none_with_less_than_two(self):
        adapter, tid, engine = _make_adapter()
        assert adapter.get_latest_two(tenant_id=tid) is None
        adapter.save_snapshot(Snapshot(
            snapshot_id="s1",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a")], edges=[],
        ), tenant_id=tid)
        assert adapter.get_latest_two(tenant_id=tid) is None
        _run(engine.dispose())

    def test_returns_correct_pair(self):
        adapter, tid, engine = _make_adapter()
        for i, sid in enumerate(["s1", "s2", "s3"]):
            adapter.save_snapshot(Snapshot(
                snapshot_id=sid,
                timestamp_start=datetime(2026, 1, 1 + i, 10, 0, 0),
                timestamp_end=datetime(2026, 1, 1 + i, 11, 0, 0),
                nodes=[Node(name="a")], edges=[],
            ), tenant_id=tid)

        result = adapter.get_latest_two(tenant_id=tid)
        assert result is not None
        previous, latest = result
        assert previous.snapshot_id == "s2"
        assert latest.snapshot_id == "s3"
        _run(engine.dispose())


class TestStorageAdapterDelete:
    """Verify delete_snapshot works."""

    def test_delete_existing(self):
        adapter, tid, engine = _make_adapter()
        adapter.save_snapshot(Snapshot(
            snapshot_id="s1",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a")], edges=[],
        ), tenant_id=tid)
        ok = adapter.delete_snapshot("s1", tenant_id=tid)
        assert ok is True
        assert adapter.load_snapshot("s1", tenant_id=tid) is None
        _run(engine.dispose())

    def test_delete_nonexistent(self):
        adapter, tid, engine = _make_adapter()
        ok = adapter.delete_snapshot("no-such", tenant_id=tid)
        assert ok is False
        _run(engine.dispose())


class TestStorageAdapterValidation:
    """Verify tenant_id validation matches old SnapshotStore behavior."""

    def test_save_requires_tenant(self):
        adapter, tid, engine = _make_adapter()
        snap = Snapshot(snapshot_id="x", nodes=[], edges=[])
        with pytest.raises(ValueError):
            adapter.save_snapshot(snap)  # no tenant_id → Ellipsis default
        with pytest.raises(ValueError):
            adapter.save_snapshot(snap, tenant_id=None)
        _run(engine.dispose())

    def test_list_requires_tenant(self):
        adapter, tid, engine = _make_adapter()
        with pytest.raises(ValueError):
            adapter.list_snapshots()  # no tenant_id
        _run(engine.dispose())
