# tests/test_builder.py
# Test graph/builder.py

import pytest
from datetime import datetime
from graph.builder import p99, _infer_node_type, build_snapshot


class TestP99:
    def test_p99_empty_list_returns_zero(self):
        """Test p99() with empty list returns 0.0"""
        assert p99([]) == 0.0

    def test_p99_single_element_returns_that_element(self):
        """Test p99() with single element returns that element"""
        assert p99([42.0]) == 42.0
        assert p99([100.5]) == 100.5

    def test_p99_with_100_elements_returns_correct_percentile(self):
        """Test p99() with 100 elements returns correct 99th percentile"""
        # For 100 elements [0, 1, 2, ..., 99], 99th percentile should be 98
        values = list(range(100))
        result = p99(values)
        # nearest-rank: idx = ceil(0.99 * 100) - 1 = 99 - 1 = 98
        # So result should be values[98] = 98
        assert result == 98

    def test_p99_with_unsorted_list(self):
        """Test p99() sorts the list correctly"""
        values = [100, 10, 50, 30, 90, 20, 70, 40, 80, 60]
        result = p99(values)
        # sorted: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        # 99th percentile of 10 elements: idx = ceil(0.99*10) - 1 = 10 - 1 = 9 (clamped)
        assert result == 100

    def test_p99_with_small_list(self):
        """Test p99() with small list"""
        assert p99([1.0, 2.0, 3.0]) == 3.0
        assert p99([5.0, 10.0]) == 10.0


class TestInferNodeType:
    def test_infer_node_type_database(self):
        """Test _infer_node_type() returns 'database' for names containing '-db'"""
        assert _infer_node_type("postgres-db") == "database"
        assert _infer_node_type("users-db") == "database"
        assert _infer_node_type("orders-db") == "database"

    def test_infer_node_type_gateway(self):
        """Test _infer_node_type() returns 'gateway' for names containing 'gateway'"""
        assert _infer_node_type("api-gateway") == "gateway"
        assert _infer_node_type("gateway-service") == "gateway"
        assert _infer_node_type("gateway") == "gateway"

    def test_infer_node_type_service(self):
        """Test _infer_node_type() returns 'service' for other names"""
        assert _infer_node_type("user-svc") == "service"
        assert _infer_node_type("order-service") == "service"
        assert _infer_node_type("payment-api") == "service"


class TestBuildSnapshot:
    def test_build_snapshot_groups_records_by_source_destination(self):
        """Test build_snapshot() correctly groups records by (source, destination)"""
        records = [
            {"source": "api", "destination": "svc-a", "status_code": 200, "latency_ms": 10.0},
            {"source": "api", "destination": "svc-a", "status_code": 200, "latency_ms": 20.0},
            {"source": "api", "destination": "svc-b", "status_code": 200, "latency_ms": 15.0},
        ]
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 11, 0, 0)
        
        snap = build_snapshot(records, start, end)
        
        assert len(snap.edges) == 2  # Two unique (source, dest) pairs
        edge_keys = [e.edge_key() for e in snap.edges]
        assert ("api", "svc-a") in edge_keys
        assert ("api", "svc-b") in edge_keys

    def test_build_snapshot_calculates_request_count(self):
        """Test build_snapshot() correctly calculates request_count"""
        records = [
            {"source": "a", "destination": "b", "status_code": 200, "latency_ms": 10.0},
            {"source": "a", "destination": "b", "status_code": 200, "latency_ms": 20.0},
            {"source": "a", "destination": "b", "status_code": 500, "latency_ms": 30.0},
        ]
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 11, 0, 0)
        
        snap = build_snapshot(records, start, end)
        
        assert len(snap.edges) == 1
        edge = snap.edges[0]
        assert edge.request_count == 3

    def test_build_snapshot_calculates_error_count(self):
        """Test build_snapshot() correctly calculates error_count (status >= 500)"""
        records = [
            {"source": "a", "destination": "b", "status_code": 200, "latency_ms": 10.0},
            {"source": "a", "destination": "b", "status_code": 404, "latency_ms": 20.0},
            {"source": "a", "destination": "b", "status_code": 500, "latency_ms": 30.0},
            {"source": "a", "destination": "b", "status_code": 503, "latency_ms": 40.0},
        ]
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 11, 0, 0)
        
        snap = build_snapshot(records, start, end)
        
        edge = snap.edges[0]
        assert edge.error_count == 2  # 500 and 503

    def test_build_snapshot_calculates_avg_latency(self):
        """Test build_snapshot() correctly calculates avg_latency_ms"""
        records = [
            {"source": "a", "destination": "b", "status_code": 200, "latency_ms": 10.0},
            {"source": "a", "destination": "b", "status_code": 200, "latency_ms": 20.0},
            {"source": "a", "destination": "b", "status_code": 200, "latency_ms": 30.0},
        ]
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 11, 0, 0)
        
        snap = build_snapshot(records, start, end)
        
        edge = snap.edges[0]
        assert edge.avg_latency_ms == 20.0  # (10+20+30)/3

    def test_build_snapshot_calculates_p99_latency(self):
        """Test build_snapshot() correctly calculates p99_latency_ms"""
        records = [
            {"source": "a", "destination": "b", "status_code": 200, "latency_ms": float(i)}
            for i in range(100)
        ]
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 11, 0, 0)
        
        snap = build_snapshot(records, start, end)
        
        edge = snap.edges[0]
        assert edge.p99_latency_ms == 98.0  # 99th percentile of [0..99]

    def test_build_snapshot_creates_correct_nodes(self):
        """Test build_snapshot() creates correct nodes from unique service names"""
        records = [
            {"source": "api-gateway", "destination": "user-svc", "status_code": 200, "latency_ms": 10.0},
            {"source": "user-svc", "destination": "users-db", "status_code": 200, "latency_ms": 15.0},
        ]
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 11, 0, 0)
        
        snap = build_snapshot(records, start, end)
        
        assert len(snap.nodes) == 3  # api-gateway, user-svc, users-db
        node_names = [n.name for n in snap.nodes]
        assert "api-gateway" in node_names
        assert "user-svc" in node_names
        assert "users-db" in node_names
        
        # Check node types are inferred correctly
        gateway = next(n for n in snap.nodes if n.name == "api-gateway")
        assert gateway.node_type == "gateway"
        
        db = next(n for n in snap.nodes if n.name == "users-db")
        assert db.node_type == "database"
        
        svc = next(n for n in snap.nodes if n.name == "user-svc")
        assert svc.node_type == "service"

    def test_build_snapshot_sets_timestamps(self):
        """Test build_snapshot() sets correct timestamps"""
        records = [
            {"source": "a", "destination": "b", "status_code": 200, "latency_ms": 10.0},
        ]
        start = datetime(2026, 1, 1, 10, 0, 0)
        end = datetime(2026, 1, 1, 11, 0, 0)
        
        snap = build_snapshot(records, start, end)
        
        assert snap.timestamp_start == start
        assert snap.timestamp_end == end
