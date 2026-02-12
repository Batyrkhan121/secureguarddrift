# tests/test_api.py
# Test API endpoints

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from api.server import app
from graph.models import Node, Edge, Snapshot
from graph.storage import SnapshotStore
from api.routes.graph_routes import init_store as init_graph_store
from api.routes.drift_routes import init_store as init_drift_store
from api.routes.report_routes import init_store as init_report_store


@pytest.fixture
def test_store(tmp_path):
    """Create a test SnapshotStore with sample data"""
    import api.server as srv
    import api.routes.graph_routes as gr
    import api.routes.drift_routes as dr
    import api.routes.report_routes as rr
    # Save original stores so we can restore after the test
    orig_server_store = srv.store
    orig_graph = gr._store
    orig_drift = dr._store
    orig_report = rr._store

    db_path = str(tmp_path / "test_api.db")
    store = SnapshotStore(db_path=db_path)
    
    # Initialize the store for all routers
    srv.store = store
    init_graph_store(store)
    init_drift_store(store)
    init_report_store(store)
    
    # Add sample snapshots
    baseline = Snapshot(
        snapshot_id="baseline-001",
        timestamp_start=datetime(2026, 2, 10, 10, 0, 0),
        timestamp_end=datetime(2026, 2, 10, 11, 0, 0),
        nodes=[
            Node(name="api-gateway", node_type="gateway"),
            Node(name="order-svc", node_type="service"),
            Node(name="orders-db", node_type="database"),
        ],
        edges=[
            Edge(source="api-gateway", destination="order-svc", 
                 request_count=100, error_count=1, avg_latency_ms=30.0, p99_latency_ms=50.0),
            Edge(source="order-svc", destination="orders-db",
                 request_count=90, error_count=0, avg_latency_ms=15.0, p99_latency_ms=25.0),
        ],
    )
    
    current = Snapshot(
        snapshot_id="current-002",
        timestamp_start=datetime(2026, 2, 10, 11, 0, 0),
        timestamp_end=datetime(2026, 2, 10, 12, 0, 0),
        nodes=[
            Node(name="api-gateway", node_type="gateway"),
            Node(name="order-svc", node_type="service"),
            Node(name="orders-db", node_type="database"),
            Node(name="payment-svc", node_type="service"),
        ],
        edges=[
            Edge(source="api-gateway", destination="order-svc",
                 request_count=100, error_count=12, avg_latency_ms=35.0, p99_latency_ms=55.0),
            Edge(source="order-svc", destination="orders-db",
                 request_count=90, error_count=0, avg_latency_ms=180.0, p99_latency_ms=250.0),
            Edge(source="order-svc", destination="payment-svc",
                 request_count=40, error_count=0, avg_latency_ms=20.0, p99_latency_ms=30.0),
        ],
    )
    
    store.save_snapshot(baseline, tenant_id="default")
    store.save_snapshot(current, tenant_id="default")
    
    yield store

    # Restore original stores so other tests are not affected
    srv.store = orig_server_store
    gr._store = orig_graph
    dr._store = orig_drift
    rr._store = orig_report


@pytest.fixture
def client(test_store):
    """Create a test client"""
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """Test GET /api/health returns 200 with status 'ok'"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "snapshots_count" in data


class TestSnapshotsEndpoint:
    def test_snapshots_returns_list(self, client):
        """Test GET /api/snapshots returns list"""
        response = client.get("/api/snapshots")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # We added 2 snapshots
        
        # Check structure
        for snapshot in data:
            assert "snapshot_id" in snapshot
            assert "timestamp_start" in snapshot
            assert "timestamp_end" in snapshot


class TestGraphLatestEndpoint:
    def test_graph_latest_returns_snapshot_data(self, client):
        """Test GET /api/graph/latest returns snapshot data"""
        response = client.get("/api/graph/latest")
        assert response.status_code == 200
        data = response.json()
        
        assert "snapshot_id" in data
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        
        # Check node structure
        if len(data["nodes"]) > 0:
            node = data["nodes"][0]
            assert "name" in node
            assert "namespace" in node
            assert "node_type" in node
        
        # Check edge structure
        if len(data["edges"]) > 0:
            edge = data["edges"][0]
            assert "source" in edge
            assert "destination" in edge
            assert "request_count" in edge
            assert "error_count" in edge
            assert "error_rate" in edge
            assert "avg_latency_ms" in edge
            assert "p99_latency_ms" in edge


class TestGraphByIdEndpoint:
    def test_graph_by_id_returns_snapshot(self, client):
        """Test GET /api/graph/{snapshot_id} returns snapshot data"""
        response = client.get("/api/graph/baseline-001")
        assert response.status_code == 200
        data = response.json()
        
        assert data["snapshot_id"] == "baseline-001"
        assert "nodes" in data
        assert "edges" in data

    def test_graph_by_id_returns_404_for_nonexistent(self, client):
        """Test GET /api/graph/{snapshot_id} returns 404 for non-existent ID"""
        response = client.get("/api/graph/nonexistent-id")
        assert response.status_code == 404


class TestDriftAnalysisEndpoint:
    def test_drift_analysis_returns_data(self, client):
        """Test GET /api/drift/ returns drift analysis"""
        response = client.get("/api/drift/")
        assert response.status_code == 200
        data = response.json()
        
        assert "baseline_id" in data
        assert "current_id" in data
        assert "events_count" in data
        assert "events" in data
        assert isinstance(data["events"], list)
        
        # Check event structure if events exist
        if data["events_count"] > 0:
            event = data["events"][0]
            assert "event_type" in event
            assert "source" in event
            assert "destination" in event
            assert "severity" in event
            assert "risk_score" in event
            assert "title" in event
            assert "what_changed" in event
            assert "why_risk" in event
            assert "affected" in event
            assert "recommendation" in event


class TestDriftSummaryEndpoint:
    def test_drift_summary_returns_counts(self, client):
        """Test GET /api/drift/summary returns severity counts"""
        response = client.get("/api/drift/summary")
        assert response.status_code == 200
        data = response.json()
        
        assert "total" in data
        assert "critical" in data
        assert "high" in data
        assert "medium" in data
        assert "low" in data
        
        # Check that counts are integers
        assert isinstance(data["total"], int)
        assert isinstance(data["critical"], int)
        assert isinstance(data["high"], int)
        assert isinstance(data["medium"], int)
        assert isinstance(data["low"], int)
        
        # Check that total equals sum of severities
        assert data["total"] == data["critical"] + data["high"] + data["medium"] + data["low"]


class TestReportJsonEndpoint:
    def test_report_json_returns_report_with_cards(self, client):
        """Test GET /api/report/json returns report with cards"""
        response = client.get("/api/report/json")
        assert response.status_code == 200
        data = response.json()
        
        assert "baseline_id" in data
        assert "current_id" in data
        assert "summary" in data
        assert "cards" in data
        
        # Check summary structure
        summary = data["summary"]
        assert "total" in summary
        assert "critical" in summary
        assert "high" in summary
        assert "medium" in summary
        assert "low" in summary
        
        # Check cards structure
        assert isinstance(data["cards"], list)
        if len(data["cards"]) > 0:
            card = data["cards"][0]
            assert "event_type" in card
            assert "title" in card
            assert "what_changed" in card
            assert "why_risk" in card
            assert "affected" in card
            assert "recommendation" in card
            assert "risk_score" in card
            assert "severity" in card


class TestDriftEndpointWithNoData:
    def test_drift_with_less_than_two_snapshots(self, tmp_path):
        """Test drift endpoints return 404 when < 2 snapshots"""
        # Create a new store with only one snapshot
        db_path = str(tmp_path / "test_single.db")
        store = SnapshotStore(db_path=db_path)
        init_graph_store(store)
        init_drift_store(store)
        init_report_store(store)
        
        snap = Snapshot(
            snapshot_id="only-one",
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a")],
            edges=[],
        )
        store.save_snapshot(snap, tenant_id="default")
        
        client = TestClient(app)
        
        response = client.get("/api/drift/")
        assert response.status_code == 404
        
        response = client.get("/api/drift/summary")
        assert response.status_code == 404
