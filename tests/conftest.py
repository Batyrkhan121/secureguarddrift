# tests/conftest.py
# Shared pytest fixtures

import pytest
from datetime import datetime
from graph.models import Node, Edge, Snapshot
from graph.storage import SnapshotStore


@pytest.fixture
def sample_nodes():
    """Sample nodes: api-gateway, order-svc, payment-svc, user-svc, payments-db, orders-db, users-db"""
    return [
        Node(name="api-gateway", node_type="gateway"),
        Node(name="order-svc", node_type="service"),
        Node(name="payment-svc", node_type="service"),
        Node(name="user-svc", node_type="service"),
        Node(name="payments-db", node_type="database"),
        Node(name="orders-db", node_type="database"),
        Node(name="users-db", node_type="database"),
    ]


@pytest.fixture
def sample_edges():
    """Sample edges with realistic metrics"""
    return [
        Edge(source="api-gateway", destination="order-svc",
             request_count=100, error_count=1, avg_latency_ms=30.0, p99_latency_ms=50.0),
        Edge(source="api-gateway", destination="user-svc",
             request_count=80, error_count=0, avg_latency_ms=25.0, p99_latency_ms=40.0),
        Edge(source="order-svc", destination="orders-db",
             request_count=90, error_count=0, avg_latency_ms=15.0, p99_latency_ms=25.0),
        Edge(source="payment-svc", destination="payments-db",
             request_count=50, error_count=1, avg_latency_ms=20.0, p99_latency_ms=35.0),
        Edge(source="user-svc", destination="users-db",
             request_count=70, error_count=0, avg_latency_ms=18.0, p99_latency_ms=30.0),
    ]


@pytest.fixture
def baseline_snapshot(sample_nodes, sample_edges):
    """Baseline snapshot for time window 10:00-11:00"""
    return Snapshot(
        snapshot_id="baseline-snap-001",
        timestamp_start=datetime(2026, 2, 10, 10, 0, 0),
        timestamp_end=datetime(2026, 2, 10, 11, 0, 0),
        nodes=sample_nodes,
        edges=sample_edges,
    )


@pytest.fixture
def current_snapshot(sample_nodes):
    """Current snapshot with drift changes for time window 11:00-12:00"""
    # New edge: order-svc -> payment-svc (new dependency)
    # Removed edge: api-gateway -> user-svc
    # Error spike: api-gateway -> order-svc (1% -> 12%)
    # Latency spike: order-svc -> orders-db (25ms -> 250ms)
    # Traffic spike: payment-svc -> payments-db (50 -> 200)
    # Blast radius: order-svc now has 3 outgoing edges (was 1)
    edges_with_drift = [
        # Existing edge with error spike
        Edge(source="api-gateway", destination="order-svc",
             request_count=100, error_count=12, avg_latency_ms=35.0, p99_latency_ms=55.0),
        # New edges for blast radius increase
        Edge(source="order-svc", destination="orders-db",
             request_count=90, error_count=0, avg_latency_ms=180.0, p99_latency_ms=250.0),
        Edge(source="order-svc", destination="payment-svc",
             request_count=40, error_count=0, avg_latency_ms=20.0, p99_latency_ms=30.0),
        Edge(source="order-svc", destination="user-svc",
             request_count=30, error_count=0, avg_latency_ms=22.0, p99_latency_ms=32.0),
        # Traffic spike
        Edge(source="payment-svc", destination="payments-db",
             request_count=200, error_count=1, avg_latency_ms=22.0, p99_latency_ms=40.0),
        # Existing edge
        Edge(source="user-svc", destination="users-db",
             request_count=70, error_count=0, avg_latency_ms=18.0, p99_latency_ms=30.0),
        # api-gateway -> user-svc removed (was in baseline)
    ]
    return Snapshot(
        snapshot_id="current-snap-002",
        timestamp_start=datetime(2026, 2, 10, 11, 0, 0),
        timestamp_end=datetime(2026, 2, 10, 12, 0, 0),
        nodes=sample_nodes,
        edges=edges_with_drift,
    )


@pytest.fixture
def tmp_db_path(tmp_path):
    """Temporary SQLite database path"""
    return str(tmp_path / "test_snapshots.db")


@pytest.fixture
def snapshot_store(tmp_db_path):
    """SnapshotStore instance using temp DB"""
    return SnapshotStore(db_path=tmp_db_path)
