# graph/builder.py
# Построение Snapshot из списка записей лога

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime

from graph.models import Node, Edge, Snapshot


def p99(values: list[float]) -> float:
    """99-й перцентиль (nearest-rank). Пустой список → 0.0."""
    if not values:
        return 0.0
    s = sorted(values)
    # nearest-rank: idx = ceil(0.99 * N) - 1, clamped to [0, N-1]
    idx = max(0, min(int(0.99 * len(s) + 0.5) - 1, len(s) - 1))
    return s[idx]


def _infer_node_type(name: str) -> str:
    """Определяет node_type по имени сервиса."""
    if "-db" in name:
        return "database"
    if "gateway" in name:
        return "gateway"
    return "service"


def build_snapshot(
    records: list[dict],
    start: datetime,
    end: datetime,
) -> Snapshot:
    """Строит Snapshot из записей лога за интервал [start, end).

    Каждая запись — dict с ключами:
        source, destination, status_code, latency_ms (и др.)
    """
    # --- Группируем по (source, destination) ---
    groups: dict[tuple[str, str], list[dict]] = {}
    for rec in records:
        key = (rec["source"], rec["destination"])
        groups.setdefault(key, []).append(rec)

    # --- Собираем уникальные имена сервисов ---
    node_names: set[str] = set()
    for src, dst in groups:
        node_names.add(src)
        node_names.add(dst)

    nodes = [
        Node(name=n, node_type=_infer_node_type(n))
        for n in sorted(node_names)
    ]

    # --- Строим рёбра ---
    edges: list[Edge] = []
    for (src, dst), recs in groups.items():
        latencies = [r["latency_ms"] for r in recs]
        request_count = len(recs)
        error_count = sum(1 for r in recs if r["status_code"] >= 500)
        avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

        edges.append(Edge(
            source=src,
            destination=dst,
            request_count=request_count,
            error_count=error_count,
            avg_latency_ms=round(avg_latency_ms, 2),
            p99_latency_ms=round(p99(latencies), 2),
        ))

    return Snapshot(
        timestamp_start=start,
        timestamp_end=end,
        edges=edges,
        nodes=nodes,
    )


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    from collector.ingress_parser import parse_log_file, get_time_windows, filter_by_time_window

    filepath = "data/mock_ingress.csv"
    records = parse_log_file(filepath)
    windows = get_time_windows(records, window_hours=1)

    start, end = windows[0]
    first_hour = filter_by_time_window(records, start, end)
    snap = build_snapshot(first_hour, start, end)

    print(f"Snapshot {snap.snapshot_id[:12]}...")
    print(f"  Period : {snap.timestamp_start} → {snap.timestamp_end}")
    print(f"  Nodes  : {len(snap.nodes)}")
    print(f"  Edges  : {len(snap.edges)}")
    for e in sorted(snap.edges, key=lambda x: x.request_count, reverse=True):
        print(f"    {e.source:20s} → {e.destination:20s}  "
              f"reqs={e.request_count:4d}  errs={e.error_count:3d}  "
              f"avg={e.avg_latency_ms:7.2f}ms  p99={e.p99_latency_ms:7.2f}ms")
