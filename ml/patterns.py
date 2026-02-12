# ml/patterns.py
"""Pattern recognition для drift events."""

from dataclasses import dataclass
from typing import Optional

from drift.detector import DriftEvent


@dataclass
class PatternResult:
    """Результат распознавания паттерна."""

    pattern_type: str  # "deployment", "canary", "error_cascade", "rollback", "unknown"
    confidence: float  # 0.0 - 1.0
    score_modifier: int  # модификатор для risk score
    explanation: str  # объяснение паттерна


def detect_deployment_pattern(events: list[DriftEvent], current_event: DriftEvent) -> Optional[PatternResult]:
    """Определяет deployment pattern: много новых edges одновременно.

    Args:
        events: все drift события в текущем batch
        current_event: текущее событие

    Returns:
        PatternResult если паттерн найден, иначе None
    """
    # Считаем количество new_edge событий
    new_edge_count = sum(1 for e in events if e.event_type == "new_edge")

    # Deployment: если >= 3 новых edges одновременно
    if new_edge_count >= 3 and current_event.event_type == "new_edge":
        return PatternResult(
            pattern_type="deployment",
            confidence=min(new_edge_count / 10.0, 1.0),  # больше edges = выше confidence
            score_modifier=-30,  # снижаем severity
            explanation=f"Deployment detected: {new_edge_count} new edges simultaneously",
        )

    return None


def detect_canary_pattern(current_event: DriftEvent) -> Optional[PatternResult]:
    """Определяет canary pattern: один edge с малым трафиком.

    Args:
        current_event: текущее событие

    Returns:
        PatternResult если паттерн найден, иначе None
    """
    if current_event.event_type != "new_edge":
        return None

    # Проверяем request_count в details
    request_count = current_event.details.get("request_count")
    
    # Если request_count не указан, пропускаем
    if request_count is None:
        return None

    # Canary: малый трафик (< 10 requests)
    if request_count > 0 and request_count < 10:
        return PatternResult(
            pattern_type="canary",
            confidence=0.8,
            score_modifier=-20,  # снижаем severity
            explanation=f"Canary release detected: only {request_count} requests",
        )

    return None


def detect_error_cascade(events: list[DriftEvent], current_event: DriftEvent) -> Optional[PatternResult]:
    """Определяет error cascade: ошибки распространяются по цепочке A→B→C.

    Args:
        events: все drift события в текущем batch
        current_event: текущее событие

    Returns:
        PatternResult если паттерн найден, иначе None
    """
    if current_event.event_type != "error_spike":
        return None

    # Считаем количество error_spike событий
    error_spike_count = sum(1 for e in events if e.event_type == "error_spike")

    # Error cascade: >= 2 error spikes одновременно
    if error_spike_count >= 2:
        # Проверяем есть ли связь между сервисами
        services_with_errors = set()
        for event in events:
            if event.event_type == "error_spike":
                services_with_errors.add(event.source)
                services_with_errors.add(event.destination)

        return PatternResult(
            pattern_type="error_cascade",
            confidence=min(error_spike_count / 5.0, 1.0),
            score_modifier=+10,  # cascade серьезнее
            explanation=f"Error cascade: {error_spike_count} errors across {len(services_with_errors)} services",
        )

    return None


def detect_rollback_pattern(events: list[DriftEvent], current_event: DriftEvent) -> Optional[PatternResult]:
    """Определяет rollback pattern: edges исчезли.

    Args:
        events: все drift события в текущем batch
        current_event: текущее событие

    Returns:
        PatternResult если паттерн найден, иначе None
    """
    # Считаем количество removed_edge событий
    removed_edge_count = sum(1 for e in events if e.event_type == "removed_edge")

    # Rollback: если >= 2 edges удалены одновременно
    if removed_edge_count >= 2 and current_event.event_type == "removed_edge":
        return PatternResult(
            pattern_type="rollback",
            confidence=min(removed_edge_count / 5.0, 1.0),
            score_modifier=-40,  # rollback обычно info only
            explanation=f"Rollback detected: {removed_edge_count} edges removed",
        )

    return None


def recognize_pattern(events: list[DriftEvent], current_event: DriftEvent) -> PatternResult:
    """Распознает паттерн для текущего события.

    Проверяет все известные паттерны и возвращает наиболее подходящий.

    Args:
        events: все drift события в текущем batch
        current_event: текущее событие

    Returns:
        PatternResult с распознанным паттерном или "unknown"
    """
    # Проверяем паттерны в порядке приоритета
    patterns = [
        detect_rollback_pattern(events, current_event),
        detect_deployment_pattern(events, current_event),
        detect_error_cascade(events, current_event),
        detect_canary_pattern(current_event),
    ]

    # Возвращаем первый найденный паттерн с достаточным confidence
    for pattern in patterns:
        if pattern and pattern.confidence >= 0.3:  # Threshold: 0.3
            return pattern

    # Если паттерн не найден
    return PatternResult(
        pattern_type="unknown",
        confidence=0.0,
        score_modifier=0,
        explanation="No known pattern detected",
    )


if __name__ == "__main__":
    # Тест deployment pattern
    events = [
        DriftEvent("new_edge", "svc-a", "svc-b", {}),
        DriftEvent("new_edge", "svc-c", "svc-d", {}),
        DriftEvent("new_edge", "svc-e", "svc-f", {}),
        DriftEvent("new_edge", "svc-g", "svc-h", {}),
    ]

    pattern = recognize_pattern(events, events[0])
    print(f"Pattern: {pattern.pattern_type}, modifier: {pattern.score_modifier}")
    print(f"  {pattern.explanation}")
