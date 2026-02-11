# tests/test_detector.py
# Test drift/detector.py

import pytest
from datetime import datetime
from graph.models import Node, Edge, Snapshot
from drift.detector import detect_drift, DriftEvent


class TestDetectDrift:
    def test_detect_drift_finds_new_edge_events(self, baseline_snapshot, current_snapshot):
        """Test detect_drift() finds new_edge events"""
        events = detect_drift(baseline_snapshot, current_snapshot)
        
        new_edge_events = [e for e in events if e.event_type == "new_edge"]
        assert len(new_edge_events) >= 1
        
        # Check that order-svc -> payment-svc is detected as new
        new_edges = [(e.source, e.destination) for e in new_edge_events]
        assert ("order-svc", "payment-svc") in new_edges

    def test_detect_drift_finds_removed_edge_events(self, baseline_snapshot, current_snapshot):
        """Test detect_drift() finds removed_edge events"""
        events = detect_drift(baseline_snapshot, current_snapshot)
        
        removed_edge_events = [e for e in events if e.event_type == "removed_edge"]
        assert len(removed_edge_events) >= 1
        
        # Check that api-gateway -> user-svc is detected as removed
        removed_edges = [(e.source, e.destination) for e in removed_edge_events]
        assert ("api-gateway", "user-svc") in removed_edges

    def test_detect_drift_finds_error_spike_events(self):
        """Test detect_drift() finds error_spike events (error_rate >2x and >0.05)"""
        baseline = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=100, error_count=2)],  # 2%
        )
        current = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 11, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 12, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=100, error_count=12)],  # 12% (>2x and >5%)
        )
        
        events = detect_drift(baseline, current)
        error_spike_events = [e for e in events if e.event_type == "error_spike"]
        
        assert len(error_spike_events) == 1
        event = error_spike_events[0]
        assert event.source == "a"
        assert event.destination == "b"
        assert event.details["baseline_value"] == pytest.approx(0.02, abs=0.001)
        assert event.details["current_value"] == pytest.approx(0.12, abs=0.001)

    def test_detect_drift_does_not_flag_error_spike_when_conditions_not_met(self):
        """Test detect_drift() does NOT flag error_spike when conditions not met"""
        # Case 1: Not > 2x
        baseline = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=100, error_count=5)],  # 5%
        )
        current = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 11, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 12, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=100, error_count=8)],  # 8% (1.6x - not >2x)
        )
        
        events = detect_drift(baseline, current)
        error_spike_events = [e for e in events if e.event_type == "error_spike"]
        assert len(error_spike_events) == 0
        
        # Case 2: Not > 0.05
        baseline2 = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=100, error_count=1)],  # 1%
        )
        current2 = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 11, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 12, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=100, error_count=3)],  # 3% (>2x but not >5%)
        )
        
        events2 = detect_drift(baseline2, current2)
        error_spike_events2 = [e for e in events2 if e.event_type == "error_spike"]
        assert len(error_spike_events2) == 0

    def test_detect_drift_finds_latency_spike_events(self):
        """Test detect_drift() finds latency_spike events (p99 >2x and >100ms)"""
        baseline = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=100, 
                       avg_latency_ms=20.0, p99_latency_ms=50.0)],
        )
        current = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 11, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 12, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=100,
                       avg_latency_ms=80.0, p99_latency_ms=150.0)],  # 3x and >100ms
        )
        
        events = detect_drift(baseline, current)
        latency_spike_events = [e for e in events if e.event_type == "latency_spike"]
        
        assert len(latency_spike_events) == 1
        event = latency_spike_events[0]
        assert event.source == "a"
        assert event.destination == "b"
        assert event.details["baseline_value"] == 50.0
        assert event.details["current_value"] == 150.0
        assert event.details["change_factor"] == 3.0

    def test_detect_drift_finds_traffic_spike_events(self):
        """Test detect_drift() finds traffic_spike events (request_count >3x)"""
        baseline = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=50)],
        )
        current = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 11, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 12, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[Edge(source="a", destination="b", request_count=200)],  # 4x
        )
        
        events = detect_drift(baseline, current)
        traffic_spike_events = [e for e in events if e.event_type == "traffic_spike"]
        
        assert len(traffic_spike_events) == 1
        event = traffic_spike_events[0]
        assert event.source == "a"
        assert event.destination == "b"
        assert event.details["baseline_value"] == 50
        assert event.details["current_value"] == 200
        assert event.details["change_factor"] == 4.0

    def test_detect_drift_finds_blast_radius_increase_events(self):
        """Test detect_drift() finds blast_radius_increase events (outgoing edges +2)"""
        baseline = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a"), Node(name="b"), Node(name="c"), Node(name="d")],
            edges=[Edge(source="a", destination="b", request_count=10)],  # a has 1 outgoing edge
        )
        current = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 11, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 12, 0, 0),
            nodes=[Node(name="a"), Node(name="b"), Node(name="c"), Node(name="d")],
            edges=[
                Edge(source="a", destination="b", request_count=10),
                Edge(source="a", destination="c", request_count=10),
                Edge(source="a", destination="d", request_count=10),
            ],  # a now has 3 outgoing edges (+2)
        )
        
        events = detect_drift(baseline, current)
        blast_radius_events = [e for e in events if e.event_type == "blast_radius_increase"]
        
        assert len(blast_radius_events) == 1
        event = blast_radius_events[0]
        assert event.source == "a"
        assert event.destination == "*"
        assert event.details["baseline_value"] == 1
        assert event.details["current_value"] == 3
        assert event.details["change_factor"] == 2

    def test_detect_drift_with_identical_snapshots_returns_empty_list(self):
        """Test detect_drift() with identical snapshots returns empty list"""
        snapshot = Snapshot(
            timestamp_start=datetime(2026, 1, 1, 10, 0, 0),
            timestamp_end=datetime(2026, 1, 1, 11, 0, 0),
            nodes=[Node(name="a"), Node(name="b")],
            edges=[
                Edge(source="a", destination="b", request_count=100, error_count=5,
                     avg_latency_ms=30.0, p99_latency_ms=50.0)
            ],
        )
        
        events = detect_drift(snapshot, snapshot)
        
        assert len(events) == 0
