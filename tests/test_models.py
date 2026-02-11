# tests/test_models.py
# Test graph/models.py

import pytest
from datetime import datetime
from graph.models import Node, Edge, Snapshot


class TestNode:
    def test_node_creation_with_defaults(self):
        """Test Node creation with default values"""
        node = Node(name="test-svc")
        assert node.name == "test-svc"
        assert node.namespace == "default"
        assert node.node_type == "service"

    def test_node_creation_with_custom_values(self):
        """Test Node creation with custom values"""
        node = Node(name="postgres-db", namespace="prod", node_type="database")
        assert node.name == "postgres-db"
        assert node.namespace == "prod"
        assert node.node_type == "database"

    def test_node_frozen_immutability(self):
        """Test that Node is frozen and immutable"""
        node = Node(name="test-svc")
        with pytest.raises(Exception):  # dataclass frozen raises FrozenInstanceError or AttributeError
            node.name = "new-name"


class TestEdge:
    def test_edge_creation_with_defaults(self):
        """Test Edge creation with default values"""
        edge = Edge(source="svc-a", destination="svc-b")
        assert edge.source == "svc-a"
        assert edge.destination == "svc-b"
        assert edge.request_count == 0
        assert edge.error_count == 0
        assert edge.avg_latency_ms == 0.0
        assert edge.p99_latency_ms == 0.0

    def test_edge_creation_with_values(self):
        """Test Edge creation with custom values"""
        edge = Edge(
            source="api-gateway",
            destination="order-svc",
            request_count=100,
            error_count=5,
            avg_latency_ms=30.5,
            p99_latency_ms=50.2,
        )
        assert edge.source == "api-gateway"
        assert edge.destination == "order-svc"
        assert edge.request_count == 100
        assert edge.error_count == 5
        assert edge.avg_latency_ms == 30.5
        assert edge.p99_latency_ms == 50.2

    def test_edge_key_returns_correct_tuple(self):
        """Test edge_key() returns (source, destination) tuple"""
        edge = Edge(source="svc-a", destination="svc-b")
        assert edge.edge_key() == ("svc-a", "svc-b")

    def test_error_rate_returns_correct_value(self):
        """Test error_rate() returns correct value"""
        edge = Edge(source="a", destination="b", request_count=100, error_count=5)
        assert edge.error_rate() == 0.05

    def test_error_rate_returns_zero_when_no_requests(self):
        """Test error_rate() returns 0.0 when request_count=0"""
        edge = Edge(source="a", destination="b", request_count=0, error_count=0)
        assert edge.error_rate() == 0.0

    def test_edge_frozen_immutability(self):
        """Test that Edge is frozen and immutable"""
        edge = Edge(source="a", destination="b")
        with pytest.raises(Exception):  # dataclass frozen raises FrozenInstanceError or AttributeError
            edge.request_count = 10


class TestSnapshot:
    def test_snapshot_creation_with_defaults(self):
        """Test Snapshot creation with auto-generated values"""
        snap = Snapshot()
        assert snap.snapshot_id is not None
        assert len(snap.snapshot_id) > 0
        assert isinstance(snap.timestamp_start, datetime)
        assert isinstance(snap.timestamp_end, datetime)
        assert snap.edges == []
        assert snap.nodes == []

    def test_snapshot_auto_generated_id_is_unique(self):
        """Test that auto-generated IDs are unique"""
        snap1 = Snapshot()
        snap2 = Snapshot()
        assert snap1.snapshot_id != snap2.snapshot_id

    def test_snapshot_with_custom_edges_and_nodes(self):
        """Test Snapshot with custom edges and nodes"""
        nodes = [Node(name="svc-a"), Node(name="svc-b")]
        edges = [Edge(source="svc-a", destination="svc-b", request_count=10)]
        snap = Snapshot(
            snapshot_id="test-snap-001",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=nodes,
            edges=edges,
        )
        assert snap.snapshot_id == "test-snap-001"
        assert snap.timestamp_start == datetime(2026, 1, 1, 10, 0, 0)
        assert snap.timestamp_end == datetime(2026, 1, 1, 11, 0, 0)
        assert len(snap.nodes) == 2
        assert len(snap.edges) == 1
        assert snap.nodes[0].name == "svc-a"
        assert snap.edges[0].source == "svc-a"
