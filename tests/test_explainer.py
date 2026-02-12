# tests/test_explainer.py
# Test drift/explainer.py

import pytest
from drift.detector import DriftEvent
from drift.explainer import explain_event, explain_all, _title, _what_changed, _recommendation


class TestTitle:
    def test_title_new_edge(self):
        """Test _title() returns correct title for new_edge"""
        event = DriftEvent(event_type="new_edge", source="svc-a", destination="svc-b")
        title = _title(event)
        assert "Новая связь" in title or "новая связь" in title.lower()
        assert "svc-a" in title
        assert "svc-b" in title

    def test_title_removed_edge(self):
        """Test _title() returns correct title for removed_edge"""
        event = DriftEvent(event_type="removed_edge", source="svc-a", destination="svc-b")
        title = _title(event)
        assert "Исчезла" in title or "исчезла" in title.lower()

    def test_title_error_spike(self):
        """Test _title() returns correct title for error_spike"""
        event = DriftEvent(event_type="error_spike", source="svc-a", destination="svc-b")
        title = _title(event)
        assert "ошибок" in title.lower() or "всплеск" in title.lower()

    def test_title_latency_spike(self):
        """Test _title() returns correct title for latency_spike"""
        event = DriftEvent(event_type="latency_spike", source="svc-a", destination="svc-b")
        title = _title(event)
        assert "задержк" in title.lower() or "латенс" in title.lower()

    def test_title_traffic_spike(self):
        """Test _title() returns correct title for traffic_spike"""
        event = DriftEvent(event_type="traffic_spike", source="svc-a", destination="svc-b")
        title = _title(event)
        assert "трафик" in title.lower()

    def test_title_blast_radius_increase(self):
        """Test _title() returns correct title for blast_radius_increase"""
        event = DriftEvent(event_type="blast_radius_increase", source="svc-a", destination="*")
        title = _title(event)
        assert "поверхност" in title.lower() or "атак" in title.lower() or "blast" in title.lower()


class TestWhatChanged:
    def test_what_changed_new_edge(self):
        """Test _what_changed() returns correct description for new_edge"""
        event = DriftEvent(
            event_type="new_edge",
            source="api-gateway",
            destination="order-svc",
            details={"description": "New edge"}
        )
        desc = _what_changed(event)
        assert "api-gateway" in desc
        assert "order-svc" in desc
        assert "новая" in desc.lower() or "появилась" in desc.lower()

    def test_what_changed_error_spike_with_formatted_values(self):
        """Test _what_changed() returns correct description with formatted values for error_spike"""
        event = DriftEvent(
            event_type="error_spike",
            source="a",
            destination="b",
            details={"baseline_value": 0.02, "current_value": 0.12, "change_factor": 6.0}
        )
        desc = _what_changed(event)
        assert "2%" in desc or "2.00%" in desc  # baseline formatted as percentage
        assert "12%" in desc or "12.00%" in desc  # current formatted as percentage
        assert "6" in desc  # change factor

    def test_what_changed_latency_spike_with_formatted_values(self):
        """Test _what_changed() returns correct description with formatted values for latency_spike"""
        event = DriftEvent(
            event_type="latency_spike",
            source="a",
            destination="b",
            details={"baseline_value": 50.0, "current_value": 150.0, "change_factor": 3.0}
        )
        desc = _what_changed(event)
        assert "50" in desc  # baseline in ms
        assert "150" in desc  # current in ms
        assert "3" in desc  # change factor

    def test_what_changed_traffic_spike_with_formatted_values(self):
        """Test _what_changed() returns correct description with formatted values for traffic_spike"""
        event = DriftEvent(
            event_type="traffic_spike",
            source="a",
            destination="b",
            details={"baseline_value": 100, "current_value": 400, "change_factor": 4.0}
        )
        desc = _what_changed(event)
        assert "100" in desc
        assert "400" in desc
        assert "4" in desc

    def test_what_changed_blast_radius_increase(self):
        """Test _what_changed() returns correct description for blast_radius_increase"""
        event = DriftEvent(
            event_type="blast_radius_increase",
            source="order-svc",
            destination="*",
            details={"baseline_value": 2, "current_value": 5}
        )
        desc = _what_changed(event)
        assert "order-svc" in desc
        assert "2" in desc
        assert "5" in desc


class TestRecommendation:
    def test_recommendation_new_edge_to_database(self):
        """Test _recommendation() returns correct recommendation for new_edge to database"""
        event = DriftEvent(event_type="new_edge", source="order-svc", destination="payments-db")
        rec = _recommendation(event)
        assert "NetworkPolicy" in rec or "проверить" in rec.lower()
        assert "payments-db" in rec or "db" in rec.lower()

    def test_recommendation_new_edge_to_service(self):
        """Test _recommendation() returns correct recommendation for new_edge to service"""
        event = DriftEvent(event_type="new_edge", source="svc-a", destination="svc-b")
        rec = _recommendation(event)
        assert "проверить" in rec.lower() or "ожидаем" in rec.lower()

    def test_recommendation_error_spike(self):
        """Test _recommendation() returns correct recommendation for error_spike"""
        event = DriftEvent(
            event_type="error_spike",
            source="a",
            destination="b",
            details={}
        )
        rec = _recommendation(event)
        assert "логи" in rec.lower() or "проверить" in rec.lower()

    def test_recommendation_latency_spike(self):
        """Test _recommendation() returns correct recommendation for latency_spike"""
        event = DriftEvent(
            event_type="latency_spike",
            source="a",
            destination="b",
            details={}
        )
        rec = _recommendation(event)
        assert "нагрузк" in rec.lower() or "rate-limiting" in rec.lower()

    def test_recommendation_removed_edge(self):
        """Test _recommendation() returns correct recommendation for removed_edge"""
        event = DriftEvent(event_type="removed_edge", source="a", destination="b")
        rec = _recommendation(event)
        assert "проверить" in rec.lower() or "ожидаем" in rec.lower()

    def test_recommendation_traffic_spike(self):
        """Test _recommendation() returns correct recommendation for traffic_spike"""
        event = DriftEvent(
            event_type="traffic_spike",
            source="a",
            destination="b",
            details={}
        )
        rec = _recommendation(event)
        assert "трафик" in rec.lower() or "rate-limiting" in rec.lower()

    def test_recommendation_blast_radius_increase(self):
        """Test _recommendation() returns correct recommendation for blast_radius_increase"""
        event = DriftEvent(
            event_type="blast_radius_increase",
            source="order-svc",
            destination="*",
            details={}
        )
        rec = _recommendation(event)
        assert "аудит" in rec.lower() or "связ" in rec.lower() or "order-svc" in rec


class TestExplainEvent:
    def test_explain_event_generates_correct_fields(self):
        """Test explain_event() generates correct ExplainCard fields"""
        event = DriftEvent(
            event_type="new_edge",
            source="order-svc",
            destination="payments-db",
            details={"description": "New edge"}
        )
        
        card = explain_event(event, score=70, severity="high")
        
        assert card.event_type == "new_edge"
        assert "order-svc" in card.title
        assert "payments-db" in card.title
        assert len(card.what_changed) > 0
        assert len(card.why_risk) > 0
        assert "order-svc" in card.affected
        assert "payments-db" in card.affected
        assert len(card.recommendation) > 0
        assert card.risk_score == 70
        assert card.severity == "high"

    def test_explain_event_includes_rule_reasons(self):
        """Test explain_event() includes reasons from triggered rules"""
        event = DriftEvent(
            event_type="new_edge",
            source="order-svc",
            destination="payments-db",
        )
        
        card = explain_event(event, score=100, severity="critical")
        
        # Should have multiple why_risk reasons from triggered rules
        assert len(card.why_risk) > 0

    def test_explain_event_with_blast_radius(self):
        """Test explain_event() handles blast_radius_increase correctly"""
        event = DriftEvent(
            event_type="blast_radius_increase",
            source="order-svc",
            destination="*",
            details={"baseline_value": 2, "current_value": 5}
        )
        
        card = explain_event(event, score=50, severity="medium")
        
        assert card.event_type == "blast_radius_increase"
        assert "order-svc" in card.affected
        # For blast_radius, destination is "*", so should only include source in affected
        assert len(card.affected) == 1


class TestExplainAll:
    def test_explain_all_returns_list_of_cards(self):
        """Test explain_all() returns list of ExplainCards matching input length"""
        events_with_scores = [
            (DriftEvent(event_type="new_edge", source="a", destination="b"), 40, "medium"),
            (DriftEvent(event_type="error_spike", source="c", destination="d",
                       details={"baseline_value": 0.02, "current_value": 0.15}), 55, "medium"),
            (DriftEvent(event_type="latency_spike", source="e", destination="f",
                       details={"baseline_value": 50, "current_value": 150}), 25, "low"),
        ]
        
        cards = explain_all(events_with_scores)
        
        assert len(cards) == 3
        assert cards[0].event_type == "new_edge"
        assert cards[1].event_type == "error_spike"
        assert cards[2].event_type == "latency_spike"
        assert cards[0].risk_score == 40
        assert cards[1].risk_score == 55
        assert cards[2].risk_score == 25

    def test_explain_all_with_empty_list(self):
        """Test explain_all() handles empty list"""
        cards = explain_all([])
        assert len(cards) == 0
