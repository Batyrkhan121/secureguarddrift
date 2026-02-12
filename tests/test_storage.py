# tests/test_storage.py
# Test graph/storage.py

import pytest
from datetime import datetime
from graph.models import Node, Edge, Snapshot
from graph.storage import SnapshotStore


class TestSnapshotStore:
    def test_creates_tables_on_init(self, tmp_db_path):
        """Test SnapshotStore creates tables on initialization"""
        store = SnapshotStore(db_path=tmp_db_path)
        
        # Verify tables exist by querying them
        import sqlite3
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        
        # Check snapshots table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snapshots'")
        assert cursor.fetchone() is not None
        
        # Check edges table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='edges'")
        assert cursor.fetchone() is not None
        
        # Check nodes table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'")
        assert cursor.fetchone() is not None
        
        conn.close()

    def test_save_and_load_snapshot_round_trip(self, snapshot_store):
        """Test save_snapshot() + load_snapshot() round-trip preserves data"""
        # Create a test snapshot
        nodes = [
            Node(name="svc-a", namespace="prod", node_type="service"),
            Node(name="svc-b", namespace="prod", node_type="database"),
        ]
        edges = [
            Edge(source="svc-a", destination="svc-b", 
                 request_count=100, error_count=5,
                 avg_latency_ms=25.5, p99_latency_ms=50.3),
        ]
        original = Snapshot(
            snapshot_id="test-snap-001",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=nodes,
            edges=edges,
        )
        
        # Save and load
        snapshot_store.save_snapshot(original)
        loaded = snapshot_store.load_snapshot("test-snap-001")
        
        # Verify data is preserved
        assert loaded is not None
        assert loaded.snapshot_id == original.snapshot_id
        assert loaded.timestamp_start == original.timestamp_start
        assert loaded.timestamp_end == original.timestamp_end
        
        assert len(loaded.nodes) == 2
        assert loaded.nodes[0].name == "svc-a"
        assert loaded.nodes[0].namespace == "prod"
        assert loaded.nodes[0].node_type == "service"
        
        assert len(loaded.edges) == 1
        assert loaded.edges[0].source == "svc-a"
        assert loaded.edges[0].destination == "svc-b"
        assert loaded.edges[0].request_count == 100
        assert loaded.edges[0].error_count == 5
        assert loaded.edges[0].avg_latency_ms == 25.5
        assert loaded.edges[0].p99_latency_ms == 50.3

    def test_load_snapshot_returns_none_for_nonexistent_id(self, snapshot_store):
        """Test load_snapshot() returns None for non-existent ID"""
        result = snapshot_store.load_snapshot("nonexistent-id")
        assert result is None

    def test_list_snapshots_returns_correct_list(self, snapshot_store):
        """Test list_snapshots() returns correct list ordered by timestamp_start"""
        # Create and save multiple snapshots
        snap1 = Snapshot(
            snapshot_id="snap-001",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a")],
            edges=[],
        )
        snap2 = Snapshot(
            snapshot_id="snap-002",
            timestamp_start=datetime(2026, 1, 1, 11, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 12, 0, 0),
            nodes=[Node(name="a")],
            edges=[],
        )
        snap3 = Snapshot(
            snapshot_id="snap-003",
            timestamp_start=datetime(2026, 1, 1, 12, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 13, 0, 0),
            nodes=[Node(name="a")],
            edges=[],
        )
        
        snapshot_store.save_snapshot(snap1)
        snapshot_store.save_snapshot(snap2)
        snapshot_store.save_snapshot(snap3)
        
        # List snapshots
        snapshots = snapshot_store.list_snapshots()
        
        assert len(snapshots) == 3
        assert snapshots[0]["snapshot_id"] == "snap-001"
        assert snapshots[1]["snapshot_id"] == "snap-002"
        assert snapshots[2]["snapshot_id"] == "snap-003"
        assert snapshots[0]["timestamp_start"] == "2026-01-01T10:00:00"
        assert snapshots[1]["timestamp_start"] == "2026-01-01T11:00:00"
        assert snapshots[2]["timestamp_start"] == "2026-01-01T12:00:00"

    def test_get_latest_two_returns_none_when_less_than_two(self, snapshot_store):
        """Test get_latest_two() returns None when < 2 snapshots"""
        # No snapshots
        assert snapshot_store.get_latest_two() is None
        
        # One snapshot
        snap = Snapshot(
            snapshot_id="snap-001",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a")],
            edges=[],
        )
        snapshot_store.save_snapshot(snap)
        assert snapshot_store.get_latest_two() is None

    def test_get_latest_two_returns_correct_tuple(self, snapshot_store):
        """Test get_latest_two() returns (previous, latest) tuple correctly"""
        # Create and save three snapshots
        snap1 = Snapshot(
            snapshot_id="snap-001",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a")],
            edges=[],
        )
        snap2 = Snapshot(
            snapshot_id="snap-002",
            timestamp_start=datetime(2026, 1, 1, 11, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 12, 0, 0),
            nodes=[Node(name="a")],
            edges=[],
        )
        snap3 = Snapshot(
            snapshot_id="snap-003",
            timestamp_start=datetime(2026, 1, 1, 12, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 13, 0, 0),
            nodes=[Node(name="a")],
            edges=[],
        )
        
        snapshot_store.save_snapshot(snap1)
        snapshot_store.save_snapshot(snap2)
        snapshot_store.save_snapshot(snap3)
        
        # Get latest two
        result = snapshot_store.get_latest_two()
        
        assert result is not None
        previous, latest = result
        assert previous.snapshot_id == "snap-002"
        assert latest.snapshot_id == "snap-003"

    def test_save_snapshot_overwrites_existing(self, snapshot_store):
        """Test save_snapshot() overwrites existing snapshot (INSERT OR REPLACE)"""
        # Save first version
        snap_v1 = Snapshot(
            snapshot_id="snap-001",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="old-node")],
            edges=[Edge(source="a", destination="b", request_count=100)],
        )
        snapshot_store.save_snapshot(snap_v1)
        
        # Save updated version with same ID
        snap_v2 = Snapshot(
            snapshot_id="snap-001",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="new-node")],
            edges=[Edge(source="x", destination="y", request_count=200)],
        )
        snapshot_store.save_snapshot(snap_v2)
        
        # Verify only one snapshot exists and it has new data
        snapshots = snapshot_store.list_snapshots()
        assert len(snapshots) == 1
        
        loaded = snapshot_store.load_snapshot("snap-001")
        assert len(loaded.nodes) == 1
        assert loaded.nodes[0].name == "new-node"
        assert len(loaded.edges) == 1
        assert loaded.edges[0].source == "x"
        assert loaded.edges[0].request_count == 200
