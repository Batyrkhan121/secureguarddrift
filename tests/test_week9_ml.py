# tests/test_week9_ml.py
"""Тесты для Week 9: ML/Intelligence."""

import os
from datetime import datetime, timedelta

import pytest

from drift.detector import DriftEvent
from graph.models import Edge, Snapshot
from ml.anomaly import calculate_anomaly_score, calculate_z_scores, is_anomaly
from ml.baseline import EdgeProfile, build_baseline, update_baseline
from ml.feedback import FeedbackRecord, FeedbackStore, calculate_feedback_modifier
from ml.patterns import detect_deployment_pattern, detect_canary_pattern, recognize_pattern
from ml.smart_scorer import calculate_smart_score, score_all_events_smart
from ml.whitelist import WhitelistEntry, WhitelistStore


def test_baseline_calculation():
    """Тест: baseline считается корректно (mean, std)."""
    snapshots = [
        Snapshot(edges=[Edge("svc-a", "svc-b", request_count=100, error_count=2, p99_latency_ms=50.0)]),
        Snapshot(edges=[Edge("svc-a", "svc-b", request_count=105, error_count=3, p99_latency_ms=52.0)]),
        Snapshot(edges=[Edge("svc-a", "svc-b", request_count=98, error_count=2, p99_latency_ms=48.0)]),
        Snapshot(edges=[Edge("svc-a", "svc-b", request_count=102, error_count=2, p99_latency_ms=51.0)]),
    ]

    baseline = build_baseline(snapshots, ("svc-a", "svc-b"))

    assert baseline is not None
    assert baseline.sample_count == 4
    assert 99 < baseline.request_count_mean < 103  # примерно 101
    assert baseline.request_count_std > 0
    assert 0.018 < baseline.error_rate_mean < 0.025  # примерно 0.022
    assert baseline.p99_latency_mean > 49 and baseline.p99_latency_mean < 52


def test_z_score_anomaly_detection():
    """Тест: Z-score аномалия детектится при z > 3."""
    baseline = EdgeProfile(
        edge_key=("svc-a", "svc-b"),
        request_count_mean=100.0,
        request_count_std=10.0,
        error_rate_mean=0.02,
        error_rate_std=0.005,
        p99_latency_mean=50.0,
        p99_latency_std=5.0,
        last_updated=datetime.utcnow(),
        sample_count=10,
    )

    # Нормальный edge
    normal_edge = Edge("svc-a", "svc-b", request_count=105, error_count=2, p99_latency_ms=52.0)
    is_anom, label, score = is_anomaly(normal_edge, baseline)
    assert is_anom is False
    assert label == "normal"
    assert score is not None and score < 2.0

    # Аномальный edge (высокая ошибка)
    anomaly_edge = Edge("svc-a", "svc-b", request_count=100, error_count=10, p99_latency_ms=50.0)
    is_anom, label, score = is_anomaly(anomaly_edge, baseline)
    assert is_anom is True
    assert label in ["anomaly", "suspicious"]
    assert score is not None and score > 3.0


def test_deployment_pattern_reduces_score():
    """Тест: Deployment pattern снижает score."""
    # Много new_edge событий
    events = [
        DriftEvent("new_edge", "svc-a", "svc-b", {}),
        DriftEvent("new_edge", "svc-c", "svc-d", {}),
        DriftEvent("new_edge", "svc-e", "svc-f", {}),
        DriftEvent("new_edge", "svc-g", "svc-h", {}),
    ]

    pattern = detect_deployment_pattern(events, events[0])
    assert pattern is not None
    assert pattern.pattern_type == "deployment"
    assert pattern.score_modifier < 0  # должен снизить score
    assert pattern.score_modifier == -30


def test_canary_pattern_detection():
    """Тест: Canary pattern распознается."""
    event = DriftEvent("new_edge", "svc-a", "svc-b", details={"request_count": 5})

    pattern = detect_canary_pattern(event)
    assert pattern is not None
    assert pattern.pattern_type == "canary"
    assert pattern.score_modifier == -20
    
    # Проверяем что без request_count pattern не срабатывает
    event_no_count = DriftEvent("new_edge", "svc-a", "svc-b", details={})
    pattern_none = detect_canary_pattern(event_no_count)
    assert pattern_none is None


def test_feedback_false_positive_reduces_score():
    """Тест: Feedback 'false_positive' снижает score в будущем."""
    # Создаем временную БД
    test_db = "/tmp/test_feedback_week9.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    store = FeedbackStore(test_db)

    # Сохраняем false_positive feedback
    feedback = FeedbackRecord(
        feedback_id=None,
        event_id="test-123",
        edge_key=("svc-a", "svc-b"),
        event_type="new_edge",
        verdict="false_positive",
        comment="Expected deployment",
        created_at=datetime.utcnow(),
    )

    store.save_feedback(feedback)

    # Получаем модификатор
    modifier = calculate_feedback_modifier(("svc-a", "svc-b"), "new_edge", store)
    assert modifier < 0  # должен снизить score
    assert modifier == -40

    # Cleanup
    os.remove(test_db)


def test_whitelist_edge_filtering():
    """Тест: Whitelist edge не генерирует event (фильтрация)."""
    # Создаем временную БД
    test_db = "/tmp/test_whitelist_week9.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    store = WhitelistStore(test_db)

    # Добавляем в whitelist
    entry = WhitelistEntry(
        entry_id=None,
        source="svc-a",
        destination="svc-b",
        reason="Known safe connection",
        created_at=datetime.utcnow(),
    )

    store.add_to_whitelist(entry)

    # Проверяем whitelist
    assert store.is_whitelisted(("svc-a", "svc-b")) is True
    assert store.is_whitelisted(("svc-c", "svc-d")) is False

    # Cleanup
    os.remove(test_db)


def test_smart_scorer_integration():
    """Тест: Smart scorer использует все модификаторы."""
    baseline = EdgeProfile(
        edge_key=("svc-a", "svc-b"),
        request_count_mean=100.0,
        request_count_std=10.0,
        error_rate_mean=0.02,
        error_rate_std=0.005,
        p99_latency_mean=50.0,
        p99_latency_std=5.0,
        last_updated=datetime.utcnow(),
        sample_count=10,
    )

    # Нормальный edge
    normal_edge = Edge("svc-a", "svc-b", request_count=105, error_count=2, p99_latency_ms=52.0)

    # Deployment pattern (много new edges - нужно минимум 3)
    events = [
        DriftEvent("new_edge", "svc-a", "svc-b", details={}),
        DriftEvent("new_edge", "svc-c", "svc-d", details={}),
        DriftEvent("new_edge", "svc-e", "svc-f", details={}),
        DriftEvent("new_edge", "svc-g", "svc-h", details={}),  # Добавляем 4-й для уверенности
    ]

    score, severity, breakdown = calculate_smart_score(
        events[0],
        events,
        baseline=baseline,
        current_edge=normal_edge,
    )

    # Должен быть base score 40 (new_edge)
    assert breakdown["base_score"] == 40

    # Должен быть anomaly modifier (normal = -20)
    assert "anomaly" in breakdown["modifiers"]
    assert breakdown["modifiers"]["anomaly"]["value"] == -20

    # Должен быть pattern modifier (deployment = -30)
    assert "pattern" in breakdown["modifiers"]
    assert breakdown["modifiers"]["pattern"]["value"] == -30

    # Final score должен быть снижен
    assert score < 40
    # 40 (base) - 20 (anomaly) - 30 (pattern) = -10, но clamp to 0
    assert score == 0 or score < 20


def test_update_baseline_incremental():
    """Тест: update_baseline обновляет профиль инкрементально."""
    # Начальный профиль
    profile = EdgeProfile(
        edge_key=("svc-a", "svc-b"),
        request_count_mean=100.0,
        request_count_std=10.0,
        error_rate_mean=0.02,
        error_rate_std=0.005,
        p99_latency_mean=50.0,
        p99_latency_std=5.0,
        last_updated=datetime.utcnow(),
        sample_count=10,
    )

    # Новый edge
    new_edge = Edge("svc-a", "svc-b", request_count=110, error_count=2, p99_latency_ms=55.0)

    # Обновляем baseline
    updated_profile = update_baseline(profile, new_edge)

    # Mean должен слегка сдвинуться
    assert updated_profile.request_count_mean > profile.request_count_mean
    assert updated_profile.request_count_mean < 110  # не равен новому значению (EMA)
    assert updated_profile.sample_count == 11


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
