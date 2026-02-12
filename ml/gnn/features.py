"""Feature extraction for GNN-based anomaly detection on service graphs."""

from __future__ import annotations

import math


def _log_norm(value: float) -> float:
    """Log-normalize a value: log(1 + x)."""
    return math.log1p(max(0.0, value))


def _z_score(value: float, mean: float, std: float) -> float:
    """Compute z-score, returns 0 if std is 0 or baseline missing."""
    if std <= 0:
        return 0.0
    return (value - mean) / std


def extract_node_features(snapshot: dict) -> dict[str, list[float]]:
    """Extract 8-dim feature vector for each node in a snapshot.

    Features: [in_degree, out_degree, is_service, is_database, is_gateway,
               avg_incoming_error_rate, avg_outgoing_error_rate,
               avg_outgoing_p99_latency_norm]
    """
    nodes = snapshot.get("nodes", [])
    edges = snapshot.get("edges", [])

    in_counts: dict[str, int] = {}
    out_counts: dict[str, int] = {}
    in_error_rates: dict[str, list[float]] = {}
    out_error_rates: dict[str, list[float]] = {}
    out_p99: dict[str, list[float]] = {}

    for e in edges:
        src, dst = e["source"], e["destination"]
        in_counts[dst] = in_counts.get(dst, 0) + 1
        out_counts[src] = out_counts.get(src, 0) + 1
        er = e.get("error_rate", 0.0)
        in_error_rates.setdefault(dst, []).append(er)
        out_error_rates.setdefault(src, []).append(er)
        out_p99.setdefault(src, []).append(e.get("p99_latency_ms", 0.0))

    max_degree = max(
        max(in_counts.values(), default=1),
        max(out_counts.values(), default=1),
        1,
    )
    max_p99 = max(
        (v for vals in out_p99.values() for v in vals),
        default=1.0,
    ) or 1.0

    result: dict[str, list[float]] = {}
    for node in nodes:
        name = node["name"]
        ntype = node.get("node_type", "service")
        in_d = in_counts.get(name, 0) / max_degree
        out_d = out_counts.get(name, 0) / max_degree
        in_er = in_error_rates.get(name, [])
        out_er = out_error_rates.get(name, [])
        op99 = out_p99.get(name, [])

        result[name] = [
            in_d,
            out_d,
            1.0 if ntype == "service" else 0.0,
            1.0 if ntype == "database" else 0.0,
            1.0 if ntype == "gateway" else 0.0,
            sum(in_er) / len(in_er) if in_er else 0.0,
            sum(out_er) / len(out_er) if out_er else 0.0,
            (sum(op99) / len(op99) / max_p99) if op99 else 0.0,
        ]
    return result


def extract_edge_features(
    edge: dict,
    baseline: dict | None = None,
    is_new: bool = False,
    edge_age_hours: float = 0.0,
    max_latency: float = 1000.0,
) -> list[float]:
    """Extract 10-dim feature vector for a single edge.

    Features: [request_count_log, error_rate, error_count_log,
               avg_latency_norm, p99_latency_norm, is_new_edge,
               z_score_requests, z_score_errors, z_score_latency,
               edge_age_hours_norm]
    """
    rc = edge.get("request_count", 0)
    er = edge.get("error_rate", 0.0)
    ec = edge.get("error_count", 0)
    avg_lat = edge.get("avg_latency_ms", 0.0)
    p99_lat = edge.get("p99_latency_ms", 0.0)
    max_lat = max(max_latency, 1.0)

    z_req, z_err, z_lat = 0.0, 0.0, 0.0
    if baseline:
        z_req = _z_score(
            rc,
            baseline.get("mean_request_count", 0),
            baseline.get("std_request_count", 0),
        )
        z_err = _z_score(
            er,
            baseline.get("mean_error_rate", 0),
            baseline.get("std_error_rate", 0),
        )
        z_lat = _z_score(
            p99_lat,
            baseline.get("mean_p99_latency", 0),
            baseline.get("std_p99_latency", 0),
        )

    return [
        _log_norm(rc),
        er,
        _log_norm(ec),
        min(avg_lat / max_lat, 1.0),
        min(p99_lat / max_lat, 1.0),
        1.0 if is_new else 0.0,
        z_req,
        z_err,
        z_lat,
        min(_log_norm(edge_age_hours) / 10.0, 1.0),
    ]
