# ml/smart_scorer.py
"""Smart scorer с ML-модификаторами для более точного scoring."""

from typing import Optional

from drift.detector import DriftEvent
from drift.scorer import BASE_SCORES, _severity_label
from graph.models import Edge
from ml.anomaly import get_anomaly_modifier, is_anomaly
from ml.baseline import EdgeProfile
from ml.patterns import PatternResult, recognize_pattern


def calculate_smart_score(
    event: DriftEvent,
    all_events: list[DriftEvent],
    baseline: Optional[EdgeProfile] = None,
    current_edge: Optional[Edge] = None,
    pattern_result: Optional[PatternResult] = None,
    history_safe: bool = False,
) -> tuple[int, str, dict]:
    """Рассчитывает smart score с учетом ML модификаторов.

    Args:
        event: текущее drift событие
        all_events: все события в batch (для pattern recognition)
        baseline: baseline профиль для edge (если есть)
        current_edge: текущее ребро из снапшота (для anomaly detection)
        pattern_result: результат pattern recognition (если уже был)
        history_safe: edge появлялся раньше и был помечен как safe

    Returns:
        (final_score, severity_label, breakdown) где breakdown - детализация score
    """
    # 1. Base score из правил
    base_score = BASE_SCORES.get(event.event_type, 10)

    breakdown = {"base_score": base_score, "modifiers": {}}

    # 2. Anomaly modifier
    anomaly_modifier = 0
    if baseline and current_edge:
        _, anomaly_label, anomaly_score = is_anomaly(current_edge, baseline)
        anomaly_modifier = get_anomaly_modifier(anomaly_score, anomaly_label)
        breakdown["modifiers"]["anomaly"] = {
            "value": anomaly_modifier,
            "reason": f"{anomaly_label} (score: {anomaly_score:.1f})" if anomaly_score else anomaly_label,
        }

    # 3. Pattern modifier
    pattern_modifier = 0
    if pattern_result is None and all_events:
        pattern_result = recognize_pattern(all_events, event)

    if pattern_result and pattern_result.pattern_type != "unknown":
        pattern_modifier = pattern_result.score_modifier
        breakdown["modifiers"]["pattern"] = {
            "value": pattern_modifier,
            "reason": f"{pattern_result.pattern_type} ({pattern_result.explanation})",
        }

    # 4. History modifier
    history_modifier = 0
    if history_safe:
        history_modifier = -40
        breakdown["modifiers"]["history"] = {"value": history_modifier, "reason": "Previously marked as safe"}

    # 5. Final score = clamp(base + all modifiers, 0, 100)
    final_score = base_score + anomaly_modifier + pattern_modifier + history_modifier
    final_score = max(0, min(100, final_score))

    severity = _severity_label(final_score)
    breakdown["final_score"] = final_score
    breakdown["severity"] = severity

    return final_score, severity, breakdown


def score_event_smart(
    event: DriftEvent,
    all_events: list[DriftEvent],
    baseline: Optional[EdgeProfile] = None,
    current_edge: Optional[Edge] = None,
    history_safe: bool = False,
) -> tuple[int, str]:
    """Оценивает событие с smart scoring и обновляет event.severity.

    Args:
        event: drift событие
        all_events: все события в batch
        baseline: baseline профиль (опционально)
        current_edge: текущее ребро (опционально)
        history_safe: edge был safe ранее

    Returns:
        (score, severity_label)
    """
    score, severity, _ = calculate_smart_score(
        event,
        all_events,
        baseline=baseline,
        current_edge=current_edge,
        history_safe=history_safe,
    )

    event.severity = severity
    return score, severity


def score_all_events_smart(
    events: list[DriftEvent],
    baselines: dict[tuple[str, str], EdgeProfile] = None,
    current_edges: dict[tuple[str, str], Edge] = None,
    history_safe_edges: set[tuple[str, str]] = None,
) -> list[tuple[DriftEvent, int, str, dict]]:
    """Оценивает все события с smart scoring.

    Args:
        events: список drift событий
        baselines: словарь edge_key -> EdgeProfile
        current_edges: словарь edge_key -> Edge
        history_safe_edges: set edge_key которые были safe

    Returns:
        Список (event, score, severity, breakdown), отсортированный по score
    """
    baselines = baselines or {}
    current_edges = current_edges or {}
    history_safe_edges = history_safe_edges or set()

    scored = []
    for event in events:
        edge_key = (event.source, event.destination)
        baseline = baselines.get(edge_key)
        current_edge = current_edges.get(edge_key)
        history_safe = edge_key in history_safe_edges

        score, severity, breakdown = calculate_smart_score(
            event,
            events,
            baseline=baseline,
            current_edge=current_edge,
            history_safe=history_safe,
        )

        event.severity = severity
        scored.append((event, score, severity, breakdown))

    # Сортировка по score убывание
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


if __name__ == "__main__":
    # Тест
    events = [
        DriftEvent("new_edge", "order-svc", "payment-db", {}),
        DriftEvent("new_edge", "user-svc", "cache-db", {}),
        DriftEvent("new_edge", "api-gateway", "user-svc", {}),
    ]

    scored = score_all_events_smart(events)
    print(f"{'source -> destination':<30s} {'type':<20s} {'score':>5s}  {'severity'}")
    print("-" * 75)
    for ev, sc, sev, bd in scored:
        edge = f"{ev.source} -> {ev.destination}"
        print(f"{edge:<30s} {ev.event_type:<20s} {sc:>5d}  {sev}")
        if "pattern" in bd["modifiers"]:
            print(f"  Pattern: {bd['modifiers']['pattern']['reason']}")
