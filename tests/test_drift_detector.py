# tests/test_drift_detector.py

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graph.models import Node, Edge, Snapshot
from drift.detector import DriftDetector, DriftEvent


def make_snapshot(nodes, edges, snap_id="snap"):
    return Snapshot(
        id=snap_id,
        nodes=[Node(id=n, name=n) for n in nodes],
        edges=[Edge(source=e[0], target=e[1], request_count=e[2] if len(e) > 2 else 10,
                     avg_latency_ms=e[3] if len(e) > 3 else 50.0,
                     error_count=e[4] if len(e) > 4 else 0)
               for e in edges],
    )


class TestDriftDetector:
    def setup_method(self):
        self.detector = DriftDetector()

    def test_no_drift(self):
        before = make_snapshot(["a", "b"], [("a", "b")], "s1")
        after = make_snapshot(["a", "b"], [("a", "b")], "s2")
        events = self.detector.compare(before, after)
        assert len(events) == 0

    def test_new_node_detected(self):
        before = make_snapshot(["a", "b"], [("a", "b")], "s1")
        after = make_snapshot(["a", "b", "c"], [("a", "b"), ("b", "c")], "s2")
        events = self.detector.compare(before, after)
        new_nodes = [e for e in events if e.drift_type == "new_node"]
        assert len(new_nodes) == 1
        assert new_nodes[0].source == "c"

    def test_removed_node_detected(self):
        before = make_snapshot(["a", "b", "c"], [("a", "b"), ("b", "c")], "s1")
        after = make_snapshot(["a", "b"], [("a", "b")], "s2")
        events = self.detector.compare(before, after)
        removed = [e for e in events if e.drift_type == "removed_node"]
        assert len(removed) == 1
        assert removed[0].source == "c"

    def test_new_edge_detected(self):
        before = make_snapshot(["a", "b", "c"], [("a", "b")], "s1")
        after = make_snapshot(["a", "b", "c"], [("a", "b"), ("a", "c")], "s2")
        events = self.detector.compare(before, after)
        new_edges = [e for e in events if e.drift_type == "new_edge"]
        assert len(new_edges) == 1
        assert new_edges[0].source == "a"
        assert new_edges[0].target == "c"

    def test_removed_edge_detected(self):
        before = make_snapshot(["a", "b", "c"], [("a", "b"), ("a", "c")], "s1")
        after = make_snapshot(["a", "b", "c"], [("a", "b")], "s2")
        events = self.detector.compare(before, after)
        removed = [e for e in events if e.drift_type == "removed_edge"]
        assert len(removed) == 1

    def test_latency_change_detected(self):
        before = make_snapshot(["a", "b"], [("a", "b", 100, 50.0, 0)], "s1")
        after = make_snapshot(["a", "b"], [("a", "b", 100, 100.0, 0)], "s2")
        events = self.detector.compare(before, after)
        metric_events = [e for e in events if e.drift_type == "metric_change"]
        assert len(metric_events) >= 1

    def test_error_rate_change_detected(self):
        before = make_snapshot(["a", "b"], [("a", "b", 100, 50.0, 5)], "s1")
        after = make_snapshot(["a", "b"], [("a", "b", 100, 50.0, 20)], "s2")
        events = self.detector.compare(before, after)
        metric_events = [e for e in events if e.drift_type == "metric_change"]
        assert len(metric_events) >= 1

    def test_drift_event_has_ids(self):
        before = make_snapshot(["a"], [], "s1")
        after = make_snapshot(["a", "b"], [("a", "b")], "s2")
        events = self.detector.compare(before, after)
        for event in events:
            assert event.id
            assert event.drift_type
