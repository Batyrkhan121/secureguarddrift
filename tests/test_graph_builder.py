# tests/test_graph_builder.py

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph.builder import GraphBuilder
from graph.models import Snapshot


class TestGraphBuilder:
    def setup_method(self):
        self.builder = GraphBuilder()

    def test_add_single_edge(self):
        self.builder.add_edge_event({
            "source": "api-gateway",
            "target": "user-service",
            "method": "GET",
            "path": "/users",
            "status_code": 200,
            "response_time_ms": 45.0,
        })
        assert self.builder.node_count == 2
        assert self.builder.edge_count == 1

    def test_add_multiple_edges(self):
        events = [
            {"source": "api-gateway", "target": "user-service", "status_code": 200, "response_time_ms": 30},
            {"source": "api-gateway", "target": "order-service", "status_code": 200, "response_time_ms": 50},
            {"source": "order-service", "target": "payment-service", "status_code": 200, "response_time_ms": 100},
        ]
        self.builder.add_edge_events(events)
        assert self.builder.node_count == 4
        assert self.builder.edge_count == 3

    def test_duplicate_edges_increment_count(self):
        for _ in range(5):
            self.builder.add_edge_event({
                "source": "a",
                "target": "b",
                "status_code": 200,
                "response_time_ms": 10,
            })
        snapshot = self.builder.build_snapshot()
        edge = snapshot.edges[0]
        assert edge.request_count == 5

    def test_error_counting(self):
        self.builder.add_edge_event({"source": "a", "target": "b", "status_code": 200, "response_time_ms": 10})
        self.builder.add_edge_event({"source": "a", "target": "b", "status_code": 500, "response_time_ms": 10})
        self.builder.add_edge_event({"source": "a", "target": "b", "status_code": 503, "response_time_ms": 10})
        snapshot = self.builder.build_snapshot()
        edge = snapshot.edges[0]
        assert edge.request_count == 3
        assert edge.error_count == 2

    def test_build_snapshot(self):
        self.builder.add_edge_event({
            "source": "gateway",
            "target": "backend",
            "status_code": 200,
            "response_time_ms": 25,
        })
        snapshot = self.builder.build_snapshot(metadata={"env": "test"})
        assert isinstance(snapshot, Snapshot)
        assert len(snapshot.nodes) == 2
        assert len(snapshot.edges) == 1
        assert snapshot.metadata["env"] == "test"

    def test_reset(self):
        self.builder.add_edge_event({"source": "a", "target": "b", "status_code": 200, "response_time_ms": 10})
        self.builder.reset()
        assert self.builder.node_count == 0
        assert self.builder.edge_count == 0

    def test_snapshot_serialization(self):
        self.builder.add_edge_event({"source": "a", "target": "b", "status_code": 200, "response_time_ms": 10})
        snapshot = self.builder.build_snapshot()
        json_str = snapshot.to_json()
        restored = Snapshot.from_json(json_str)
        assert len(restored.nodes) == len(snapshot.nodes)
        assert len(restored.edges) == len(snapshot.edges)
