# drift/detector.py
# Сравнение двух снапшотов (baseline vs current): поиск drift-событий

from dataclasses import dataclass, field
from graph.models import Snapshot, Edge


@dataclass
class DriftEvent:
    """Одно drift-событие между baseline и current снапшотами."""
    event_type: str       # "new_edge" | "removed_edge" | "error_spike" |
                          # "latency_spike" | "traffic_spike" | "blast_radius_increase"
    source: str
    destination: str
    severity: str = "medium"
    details: dict = field(default_factory=dict)


def _outgoing_counts(snap: Snapshot) -> dict[str, int]:
    """Количество исходящих edges для каждого source-сервиса."""
    counts: dict[str, int] = {}
    for e in snap.edges:
        counts[e.source] = counts.get(e.source, 0) + 1
    return counts


def detect_drift(baseline: Snapshot, current: Snapshot) -> list[DriftEvent]:
    """Сравнивает baseline и current, возвращает список DriftEvent.

    Правила:
      1. new_edge        — есть в current, нет в baseline
      2. removed_edge    — есть в baseline, нет в current
      3. error_spike     — error_rate выросла >2x И current > 0.05
      4. latency_spike   — p99_latency выросла >2x И current p99 > 100ms
      5. traffic_spike   — request_count вырос >3x
      6. blast_radius_increase — исходящих edges у сервиса стало на 2+ больше
    """
    events: list[DriftEvent] = []

    base_map: dict[tuple[str, str], Edge] = {e.edge_key(): e for e in baseline.edges}
    curr_map: dict[tuple[str, str], Edge] = {e.edge_key(): e for e in current.edges}
    base_keys = set(base_map)
    curr_keys = set(curr_map)

    # 1. New edges
    for key in sorted(curr_keys - base_keys):
        events.append(DriftEvent(
            event_type="new_edge", source=key[0], destination=key[1],
            details={"description": f"New edge {key[0]} -> {key[1]}"},
        ))

    # 2. Removed edges
    for key in sorted(base_keys - curr_keys):
        events.append(DriftEvent(
            event_type="removed_edge", source=key[0], destination=key[1],
            details={"description": f"Removed edge {key[0]} -> {key[1]}"},
        ))

    # 3-5. Metric changes on common edges
    for key in sorted(base_keys & curr_keys):
        old, new = base_map[key], curr_map[key]

        # 3. Error spike
        old_er, new_er = old.error_rate(), new.error_rate()
        if old_er > 0 and new_er > 0.05 and new_er / old_er > 2:
            events.append(DriftEvent(
                event_type="error_spike", source=key[0], destination=key[1],
                details={"baseline_value": round(old_er, 4),
                         "current_value": round(new_er, 4),
                         "change_factor": round(new_er / old_er, 2)},
            ))

        # 4. Latency spike
        if old.p99_latency_ms > 0 and new.p99_latency_ms > 100:
            factor = new.p99_latency_ms / old.p99_latency_ms
            if factor > 2:
                events.append(DriftEvent(
                    event_type="latency_spike", source=key[0], destination=key[1],
                    details={"baseline_value": old.p99_latency_ms,
                             "current_value": new.p99_latency_ms,
                             "change_factor": round(factor, 2)},
                ))

        # 5. Traffic spike
        if old.request_count > 0:
            factor = new.request_count / old.request_count
            if factor > 3:
                events.append(DriftEvent(
                    event_type="traffic_spike", source=key[0], destination=key[1],
                    details={"baseline_value": old.request_count,
                             "current_value": new.request_count,
                             "change_factor": round(factor, 2)},
                ))

    # 6. Blast radius increase
    base_out = _outgoing_counts(baseline)
    curr_out = _outgoing_counts(current)
    for svc in sorted(set(base_out) | set(curr_out)):
        diff = curr_out.get(svc, 0) - base_out.get(svc, 0)
        if diff >= 2:
            events.append(DriftEvent(
                event_type="blast_radius_increase", source=svc, destination="*",
                details={"baseline_value": base_out.get(svc, 0),
                         "current_value": curr_out.get(svc, 0),
                         "change_factor": diff},
            ))

    return events


if __name__ == "__main__":
    from datetime import datetime
    from graph.models import Node, Edge, Snapshot

    baseline = Snapshot(
        timestamp_start=datetime(2026, 1, 1, 10, 0),
        timestamp_end=datetime(2026, 1, 1, 11, 0),
        nodes=[Node(name="api-gateway", node_type="gateway"),
               Node(name="order-svc"), Node(name="payments-db", node_type="database")],
        edges=[
            Edge(source="api-gateway", destination="order-svc",
                 request_count=100, error_count=1, avg_latency_ms=30, p99_latency_ms=50),
            Edge(source="order-svc", destination="payments-db",
                 request_count=80, error_count=1, avg_latency_ms=15, p99_latency_ms=25),
        ],
    )

    current = Snapshot(
        timestamp_start=datetime(2026, 1, 1, 11, 0),
        timestamp_end=datetime(2026, 1, 1, 12, 0),
        nodes=[Node(name="api-gateway", node_type="gateway"),
               Node(name="order-svc"), Node(name="payments-db", node_type="database"),
               Node(name="user-svc"), Node(name="orders-db", node_type="database")],
        edges=[
            Edge(source="api-gateway", destination="order-svc",
                 request_count=100, error_count=12, avg_latency_ms=35, p99_latency_ms=55),
            Edge(source="order-svc", destination="payments-db",
                 request_count=80, error_count=1, avg_latency_ms=180, p99_latency_ms=250),
            Edge(source="order-svc", destination="orders-db",
                 request_count=50, error_count=0, avg_latency_ms=10, p99_latency_ms=18),
            Edge(source="order-svc", destination="user-svc",
                 request_count=40, error_count=0, avg_latency_ms=20, p99_latency_ms=30),
        ],
    )

    events = detect_drift(baseline, current)
    print(f"Drift events: {len(events)}")
    for ev in events:
        print(f"  [{ev.event_type:24s}] {ev.source:15s} -> {ev.destination:15s}  {ev.details}")
