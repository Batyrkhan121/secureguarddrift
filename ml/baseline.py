# ml/baseline.py
"""Baseline profiling для определения нормального поведения каждого edge."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from graph.models import Edge, Snapshot


@dataclass
class EdgeProfile:
    """Профиль baseline для edge: mean и std для метрик."""

    edge_key: tuple[str, str]
    request_count_mean: float
    request_count_std: float
    error_rate_mean: float
    error_rate_std: float
    p99_latency_mean: float
    p99_latency_std: float
    last_updated: datetime
    sample_count: int  # количество снапшотов в расчете


def build_baseline(
    snapshots: list[Snapshot],
    edge_key: tuple[str, str],
    window_size: int = 24,
) -> Optional[EdgeProfile]:
    """Строит baseline профиль для edge на основе последних N снапшотов.

    Args:
        snapshots: список снапшотов (отсортированный по времени, новые в конце)
        edge_key: (source, destination)
        window_size: размер окна скольжения (по умолчанию 24)

    Returns:
        EdgeProfile или None если недостаточно данных
    """
    # Берем последние N снапшотов
    recent_snapshots = snapshots[-window_size:] if len(snapshots) > window_size else snapshots

    # Собираем метрики для этого edge из снапшотов
    request_counts = []
    error_rates = []
    p99_latencies = []

    for snapshot in recent_snapshots:
        for edge in snapshot.edges:
            if edge.edge_key() == edge_key:
                request_counts.append(edge.request_count)
                error_rates.append(edge.error_rate())
                p99_latencies.append(edge.p99_latency_ms)
                break

    # Нужно хотя бы 3 точки для расчета статистики
    if len(request_counts) < 3:
        return None

    # Расчет mean и std
    return EdgeProfile(
        edge_key=edge_key,
        request_count_mean=float(np.mean(request_counts)),
        request_count_std=float(np.std(request_counts)),
        error_rate_mean=float(np.mean(error_rates)),
        error_rate_std=float(np.std(error_rates)),
        p99_latency_mean=float(np.mean(p99_latencies)),
        p99_latency_std=float(np.std(p99_latencies)),
        last_updated=datetime.now(timezone.utc),
        sample_count=len(request_counts),
    )


def update_baseline(
    current_profile: Optional[EdgeProfile],
    new_edge: Edge,
    window_size: int = 24,
) -> EdgeProfile:
    """Обновляет baseline с новым edge (incremental update).

    Использует экспоненциальное скользящее среднее для обновления.

    Args:
        current_profile: текущий профиль или None
        new_edge: новое ребро из нового снапшота
        window_size: размер окна для расчета веса

    Returns:
        Обновленный EdgeProfile
    """
    if current_profile is None:
        # Первый снапшот - инициализация
        return EdgeProfile(
            edge_key=new_edge.edge_key(),
            request_count_mean=float(new_edge.request_count),
            request_count_std=0.0,
            error_rate_mean=new_edge.error_rate(),
            error_rate_std=0.0,
            p99_latency_mean=float(new_edge.p99_latency_ms),
            p99_latency_std=0.0,
            last_updated=datetime.now(timezone.utc),
            sample_count=1,
        )

    # Exponential moving average weight
    alpha = 2.0 / (window_size + 1)

    # Обновление mean с EMA
    new_request_mean = (1 - alpha) * current_profile.request_count_mean + alpha * new_edge.request_count
    new_error_mean = (1 - alpha) * current_profile.error_rate_mean + alpha * new_edge.error_rate()
    new_latency_mean = (1 - alpha) * current_profile.p99_latency_mean + alpha * new_edge.p99_latency_ms

    # Обновление std (приближенно через variance)
    request_var = current_profile.request_count_std**2
    new_request_var = (1 - alpha) * request_var + alpha * (new_edge.request_count - new_request_mean) ** 2

    error_var = current_profile.error_rate_std**2
    new_error_var = (1 - alpha) * error_var + alpha * (new_edge.error_rate() - new_error_mean) ** 2

    latency_var = current_profile.p99_latency_std**2
    new_latency_var = (1 - alpha) * latency_var + alpha * (new_edge.p99_latency_ms - new_latency_mean) ** 2

    return EdgeProfile(
        edge_key=new_edge.edge_key(),
        request_count_mean=new_request_mean,
        request_count_std=np.sqrt(new_request_var),
        error_rate_mean=new_error_mean,
        error_rate_std=np.sqrt(new_error_var),
        p99_latency_mean=new_latency_mean,
        p99_latency_std=np.sqrt(new_latency_var),
        last_updated=datetime.now(timezone.utc),
        sample_count=min(current_profile.sample_count + 1, window_size),
    )


if __name__ == "__main__":
    # Тест
    snapshots = [
        Snapshot(edges=[Edge("svc-a", "svc-b", request_count=100, error_count=2, p99_latency_ms=50.0)]),
        Snapshot(edges=[Edge("svc-a", "svc-b", request_count=105, error_count=3, p99_latency_ms=52.0)]),
        Snapshot(edges=[Edge("svc-a", "svc-b", request_count=98, error_count=2, p99_latency_ms=48.0)]),
        Snapshot(edges=[Edge("svc-a", "svc-b", request_count=102, error_count=2, p99_latency_ms=51.0)]),
    ]

    profile = build_baseline(snapshots, ("svc-a", "svc-b"))
    if profile:
        print("Baseline для ('svc-a', 'svc-b'):")
        print(f"  request_count: {profile.request_count_mean:.1f} ± {profile.request_count_std:.1f}")
        print(f"  error_rate: {profile.error_rate_mean:.3f} ± {profile.error_rate_std:.3f}")
        print(f"  p99_latency: {profile.p99_latency_mean:.1f} ± {profile.p99_latency_std:.1f}")
        print(f"  samples: {profile.sample_count}")
