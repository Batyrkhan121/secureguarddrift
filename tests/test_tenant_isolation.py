# tests/test_tenant_isolation.py
# Multi-tenancy isolation tests

import pytest
from datetime import datetime
from graph.models import Node, Edge, Snapshot
from graph.storage import SnapshotStore


@pytest.fixture
def store(tmp_path):
    return SnapshotStore(db_path=str(tmp_path / "tenant_test.db"))


def _snap(sid, hour):
    return Snapshot(
        snapshot_id=sid,
        timestamp_start=datetime(2026, 1, 1, hour, 0, 0),
        timestamp_end=datetime(2026, 1, 1, hour + 1, 0, 0),
        nodes=[Node(name="svc-a")],
        edges=[Edge(source="svc-a", destination="svc-b", request_count=10)],
    )


class TestTenantIsolation:
    def test_tenant_a_sees_only_own_snapshots(self, store):
        store.save_snapshot(_snap("snap-a1", 10), tenant_id="tenant_a")
        store.save_snapshot(_snap("snap-b1", 11), tenant_id="tenant_b")

        result = store.list_snapshots(tenant_id="tenant_a")
        ids = [r["snapshot_id"] for r in result]
        assert ids == ["snap-a1"]

    def test_tenant_b_sees_only_own_snapshots(self, store):
        store.save_snapshot(_snap("snap-a1", 10), tenant_id="tenant_a")
        store.save_snapshot(_snap("snap-b1", 11), tenant_id="tenant_b")

        result = store.list_snapshots(tenant_id="tenant_b")
        ids = [r["snapshot_id"] for r in result]
        assert ids == ["snap-b1"]

    def test_super_admin_sees_all(self, store):
        store.save_snapshot(_snap("snap-a1", 10), tenant_id="tenant_a")
        store.save_snapshot(_snap("snap-b1", 11), tenant_id="tenant_b")

        result = store.list_snapshots(tenant_id=None)
        ids = sorted(r["snapshot_id"] for r in result)
        assert ids == ["snap-a1", "snap-b1"]

    def test_load_foreign_snapshot_returns_none(self, store):
        store.save_snapshot(_snap("snap-a1", 10), tenant_id="tenant_a")

        # tenant_b tries to load tenant_a's snapshot → None (not 403)
        assert store.load_snapshot("snap-a1", tenant_id="tenant_b") is None

    def test_super_admin_loads_any_snapshot(self, store):
        store.save_snapshot(_snap("snap-a1", 10), tenant_id="tenant_a")

        loaded = store.load_snapshot("snap-a1", tenant_id=None)
        assert loaded is not None
        assert loaded.snapshot_id == "snap-a1"

    def test_get_latest_two_isolated(self, store):
        store.save_snapshot(_snap("snap-a1", 10), tenant_id="tenant_a")
        store.save_snapshot(_snap("snap-a2", 11), tenant_id="tenant_a")
        store.save_snapshot(_snap("snap-b1", 12), tenant_id="tenant_b")

        pair = store.get_latest_two(tenant_id="tenant_a")
        assert pair is not None
        assert pair[0].snapshot_id == "snap-a1"
        assert pair[1].snapshot_id == "snap-a2"

        # tenant_b has only 1 snapshot → None
        assert store.get_latest_two(tenant_id="tenant_b") is None

    def test_delete_isolated(self, store):
        store.save_snapshot(_snap("snap-a1", 10), tenant_id="tenant_a")
        store.save_snapshot(_snap("snap-b1", 11), tenant_id="tenant_b")

        # tenant_b cannot delete tenant_a's snapshot
        assert store.delete_snapshot("snap-a1", tenant_id="tenant_b") is False
        # snap-a1 still exists
        assert store.load_snapshot("snap-a1", tenant_id="tenant_a") is not None

    def test_missing_tenant_id_raises(self, store):
        with pytest.raises(ValueError, match="tenant_id required"):
            store.list_snapshots()
        with pytest.raises(ValueError, match="tenant_id required"):
            store.load_snapshot("x")
        with pytest.raises(ValueError, match="tenant_id required"):
            store.save_snapshot(_snap("x", 10))
