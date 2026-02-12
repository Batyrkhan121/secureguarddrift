# ml/anomaly.py
"""Anomaly detection с Z-score для drift events."""

from dataclasses import dataclass
from typing import Optional

from graph.models import Edge
from ml.baseline import EdgeProfile


@dataclass
class ZScores:
    """Z-scores для метрик edge."""

    request_count_z: float
    error_rate_z: float
    p99_latency_z: float


# Веса для расчета итогового anomaly score
METRIC_WEIGHTS = {
    "error_rate": 2.0,  # Ошибки важнее всего
    "p99_latency": 1.5,  # Латентность тоже важна
    "request_count": 1.0,  # Изменение трафика менее критично
}


def calculate_z_scores(
    current_edge: Edge,
    baseline: EdgeProfile,
) -> ZScores:
    """Рассчитывает z-scores для edge относительно baseline.

    Z-score показывает на сколько стандартных отклонений текущее
    значение отличается от среднего.

    z = (current - mean) / std

    Args:
        current_edge: текущее ребро
        baseline: baseline профиль

    Returns:
        ZScores с z-scores для всех метрик
    """
    # Request count z-score
    if baseline.request_count_std > 0:
        request_z = (current_edge.request_count - baseline.request_count_mean) / baseline.request_count_std
    else:
        request_z = 0.0

    # Error rate z-score
    current_error_rate = current_edge.error_rate()
    if baseline.error_rate_std > 0:
        error_z = (current_error_rate - baseline.error_rate_mean) / baseline.error_rate_std
    else:
        error_z = 0.0

    # P99 latency z-score
    if baseline.p99_latency_std > 0:
        latency_z = (current_edge.p99_latency_ms - baseline.p99_latency_mean) / baseline.p99_latency_std
    else:
        latency_z = 0.0

    return ZScores(
        request_count_z=request_z,
        error_rate_z=error_z,
        p99_latency_z=latency_z,
    )


def calculate_anomaly_score(z_scores: ZScores) -> float:
    """Рассчитывает итоговый anomaly score как взвешенную сумму z-scores.

    Используем только положительные z-scores (ухудшения),
    и берем absolute value для нейтральных метрик.

    Args:
        z_scores: Z-scores для метрик

    Returns:
        Anomaly score (обычно в диапазоне 0-10+)
    """
    # Для error_rate и latency: берем только положительные (ухудшения)
    error_contribution = max(0, z_scores.error_rate_z) * METRIC_WEIGHTS["error_rate"]
    latency_contribution = max(0, z_scores.p99_latency_z) * METRIC_WEIGHTS["p99_latency"]

    # Для request_count: любое отклонение может быть интересно
    request_contribution = abs(z_scores.request_count_z) * METRIC_WEIGHTS["request_count"]

    anomaly_score = error_contribution + latency_contribution + request_contribution

    return anomaly_score


def is_anomaly(
    current_edge: Edge,
    baseline: Optional[EdgeProfile],
    threshold_anomaly: float = 3.0,
    threshold_suspicious: float = 2.0,
) -> tuple[bool, str, Optional[float]]:
    """Определяет является ли edge аномалией.

    Args:
        current_edge: текущее ребро
        baseline: baseline профиль (может быть None)
        threshold_anomaly: порог для аномалии (по умолчанию 3.0)
        threshold_suspicious: порог для подозрительности (по умолчанию 2.0)

    Returns:
        (is_anomaly, label, anomaly_score)
        - is_anomaly: True если аномалия или подозрительно
        - label: "anomaly" / "suspicious" / "normal"
        - anomaly_score: числовой score или None
    """
    if baseline is None:
        # Нет baseline - не можем определить аномалию
        return False, "no_baseline", None

    # Недостаточно данных для статистики
    if baseline.sample_count < 3:
        return False, "insufficient_data", None

    z_scores = calculate_z_scores(current_edge, baseline)
    anomaly_score = calculate_anomaly_score(z_scores)

    # Проверка порогов
    if anomaly_score >= threshold_anomaly:
        return True, "anomaly", anomaly_score
    elif anomaly_score >= threshold_suspicious:
        return True, "suspicious", anomaly_score
    else:
        return False, "normal", anomaly_score


def get_anomaly_modifier(anomaly_score: Optional[float], label: str) -> int:
    """Возвращает модификатор для risk score на основе anomaly detection.

    Args:
        anomaly_score: числовой anomaly score
        label: "anomaly" / "suspicious" / "normal" / "no_baseline"

    Returns:
        Модификатор для добавления к base score (-20 до +20)
    """
    if label == "no_baseline" or label == "insufficient_data":
        return 0  # Нейтрально

    if label == "anomaly":
        return +20  # Подтвержденная аномалия - повысить риск
    elif label == "suspicious":
        return +10  # Подозрительно - немного повысить
    else:  # normal
        return -20  # В пределах нормы - снизить риск


if __name__ == "__main__":
    from ml.baseline import EdgeProfile

    # Пример baseline
    baseline = EdgeProfile(
        edge_key=("svc-a", "svc-b"),
        request_count_mean=100.0,
        request_count_std=10.0,
        error_rate_mean=0.02,
        error_rate_std=0.005,
        p99_latency_mean=50.0,
        p99_latency_std=5.0,
        last_updated=None,
        sample_count=10,
    )

    # Нормальный edge
    normal_edge = Edge("svc-a", "svc-b", request_count=105, error_count=2, p99_latency_ms=52.0)
    is_anom, label, score = is_anomaly(normal_edge, baseline)
    print(f"Normal edge: is_anomaly={is_anom}, label={label}, score={score:.2f if score else 'N/A'}")

    # Аномальный edge (высокая ошибка)
    anomaly_edge = Edge("svc-a", "svc-b", request_count=100, error_count=10, p99_latency_ms=50.0)
    is_anom, label, score = is_anomaly(anomaly_edge, baseline)
    print(f"Anomaly edge: is_anomaly={is_anom}, label={label}, score={score:.2f if score else 'N/A'}")
