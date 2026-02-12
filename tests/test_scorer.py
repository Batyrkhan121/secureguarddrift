# tests/test_scorer.py
# Test drift/scorer.py

import pytest
from drift.detector import DriftEvent
from drift.scorer import score_event, score_all_events, _severity_label


class TestSeverityLabel:
    def test_severity_label_critical(self):
        """Test _severity_label() returns 'critical' for >= 80"""
        assert _severity_label(80) == "critical"
        assert _severity_label(90) == "critical"
        assert _severity_label(100) == "critical"

    def test_severity_label_high(self):
        """Test _severity_label() returns 'high' for >= 60"""
        assert _severity_label(60) == "high"
        assert _severity_label(70) == "high"
        assert _severity_label(79) == "high"

    def test_severity_label_medium(self):
        """Test _severity_label() returns 'medium' for >= 40"""
        assert _severity_label(40) == "medium"
        assert _severity_label(50) == "medium"
        assert _severity_label(59) == "medium"

    def test_severity_label_low(self):
        """Test _severity_label() returns 'low' for < 40"""
        assert _severity_label(0) == "low"
        assert _severity_label(20) == "low"
        assert _severity_label(39) == "low"


class TestScoreEvent:
    def test_score_event_returns_correct_base_score(self):
        """Test score_event() returns correct base score + rule boosts"""
        # removed_edge event with no rules triggered
        event = DriftEvent(
            event_type="removed_edge",
            source="svc-a",
            destination="svc-b",
        )
        score, severity = score_event(event)
        
        # Base score for removed_edge is 20
        assert score == 20
        assert severity == "low"
        assert event.severity == "low"

    def test_score_event_with_rule_boosts(self):
        """Test score_event() includes rule boosts"""
        # new_edge to sensitive service (payments-db)
        # Should trigger: sensitive_target (+30), database_direct_access (+30), bypass_gateway (+20)
        event = DriftEvent(
            event_type="new_edge",
            source="order-svc",
            destination="payments-db",
        )
        score, severity = score_event(event)
        
        # Base score: 40
        # sensitive_target: +30
        # database_direct_access: +30
        # bypass_gateway: +20
        # Total: 40 + 30 + 30 + 20 = 120, clamped to 100
        assert score == 100
        assert severity == "critical"
        assert event.severity == "critical"

    def test_score_event_clamped_at_100(self):
        """Test score_event() clamps score at 100"""
        # Create an event that would exceed 100
        event = DriftEvent(
            event_type="new_edge",
            source="user-svc",
            destination="users-db",
        )
        score, severity = score_event(event)
        
        # Base: 40 + sensitive_target: 30 + database_direct_access: 30 + bypass_gateway: 20 = 120 -> 100
        assert score <= 100

    def test_score_event_sets_severity_on_event(self):
        """Test score_event() sets event.severity correctly"""
        event = DriftEvent(
            event_type="removed_edge",
            source="a",
            destination="b",
        )
        score, severity = score_event(event)
        
        # Base score for removed_edge is 20
        assert event.severity == severity
        assert severity == "low"


class TestScoreAllEvents:
    def test_score_all_events_sorts_by_score_descending(self):
        """Test score_all_events() sorts by score descending"""
        events = [
            DriftEvent(event_type="removed_edge", source="a", destination="b"),  # 20
            DriftEvent(event_type="new_edge", source="order-svc", destination="payments-db"),  # 100
            DriftEvent(event_type="latency_spike", source="x", destination="y",
                      details={"baseline_value": 50, "current_value": 150}),  # 25
        ]
        
        scored = score_all_events(events)
        
        assert len(scored) == 3
        # Should be sorted by score descending
        assert scored[0][1] >= scored[1][1]
        assert scored[1][1] >= scored[2][1]
        
        # First should be the new_edge to payments-db (highest score)
        assert scored[0][0].event_type == "new_edge"
        assert scored[0][0].destination == "payments-db"

    def test_score_all_events_returns_correct_tuples(self):
        """Test score_all_events() returns list of (event, score, severity) tuples"""
        events = [
            DriftEvent(event_type="new_edge", source="a", destination="b"),
        ]
        
        scored = score_all_events(events)
        
        assert len(scored) == 1
        event, score, severity = scored[0]
        assert isinstance(event, DriftEvent)
        assert isinstance(score, int)
        assert isinstance(severity, str)
        assert severity in ["critical", "high", "medium", "low"]

    def test_score_all_events_with_various_event_types(self):
        """Test score_all_events() handles various event types correctly"""
        events = [
            DriftEvent(event_type="new_edge", source="a", destination="b"),
            DriftEvent(event_type="removed_edge", source="c", destination="d"),
            DriftEvent(event_type="error_spike", source="e", destination="f",
                      details={"baseline_value": 0.02, "current_value": 0.15}),
            DriftEvent(event_type="latency_spike", source="g", destination="h",
                      details={"baseline_value": 50, "current_value": 150}),
            DriftEvent(event_type="traffic_spike", source="i", destination="j",
                      details={"baseline_value": 100, "current_value": 400}),
            DriftEvent(event_type="blast_radius_increase", source="k", destination="*",
                      details={"baseline_value": 2, "current_value": 5}),
        ]
        
        scored = score_all_events(events)
        
        assert len(scored) == 6
        # All events should have scores and severities
        for event, score, severity in scored:
            assert score >= 0
            assert score <= 100
            assert severity in ["critical", "high", "medium", "low"]
