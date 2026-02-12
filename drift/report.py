# drift/report.py
# Генерация Markdown-отчёта по drift-анализу

import os
from datetime import datetime
from graph.models import Snapshot
from drift.explainer import ExplainCard


def generate_report(
    baseline: Snapshot,
    current: Snapshot,
    cards: list[ExplainCard],
    output_path: str = "reports/drift_report.md",
) -> str:
    """Генерирует Markdown-отчёт и сохраняет в файл.

    Возвращает содержимое отчёта как строку.
    """
    # --- Подсчёт сводки ---
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    type_counts = {"new_edge": 0, "removed_edge": 0}
    for c in cards:
        sev_counts[c.severity] = sev_counts.get(c.severity, 0) + 1
        if c.event_type in type_counts:
            type_counts[c.event_type] += 1

    # --- Заголовок ---
    lines: list[str] = [
        "# SecureGuard Drift Report",
        "",
        f"**Период анализа:** {baseline.timestamp_start} — {current.timestamp_end}  ",
        f"**Baseline снапшот:** {baseline.snapshot_id} "
        f"({baseline.timestamp_start} — {baseline.timestamp_end})  ",
        f"**Текущий снапшот:** {current.snapshot_id} "
        f"({current.timestamp_start} — {current.timestamp_end})",
        "",
    ]

    # --- Сводка ---
    lines += [
        "## Сводка",
        "",
        "| Метрика | Значение |",
        "|---------|----------|",
        f"| Всего drift-событий | {len(cards)} |",
        f"| Critical | {sev_counts['critical']} |",
        f"| High | {sev_counts['high']} |",
        f"| Medium | {sev_counts['medium']} |",
        f"| Low | {sev_counts['low']} |",
        f"| Новых связей | {type_counts['new_edge']} |",
        f"| Исчезнувших связей | {type_counts['removed_edge']} |",
        "",
    ]

    # --- Drift-события ---
    lines.append("## Drift-события (по убыванию риска)")
    lines.append("")

    for i, card in enumerate(cards, 1):
        sev_tag = card.severity.upper()
        lines.append(f"### {i}. [{sev_tag}] {card.title} (Score: {card.risk_score})")
        lines.append("")
        lines.append(f"**Что изменилось:** {card.what_changed}  ")
        lines.append("**Почему это риск:**")
        for reason in card.why_risk:
            lines.append(f"- {reason}")
        lines.append("")
        lines.append(f"**Затронутые сервисы:** {', '.join(card.affected)}  ")
        lines.append(f"**Рекомендация:** {card.recommendation}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # --- Рекомендации (уникальные) ---
    seen: set[str] = set()
    unique_recs: list[str] = []
    for card in cards:
        if card.recommendation not in seen:
            seen.add(card.recommendation)
            unique_recs.append(card.recommendation)

    lines.append("## Рекомендации")
    lines.append("")
    for j, rec in enumerate(unique_recs, 1):
        lines.append(f"{j}. {rec}")
    lines.append("")

    # --- Футер ---
    lines += [
        "---",
        "*Отчёт сгенерирован SecureGuard Drift v0.1*  ",
        f"*{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
    ]

    content = "\n".join(lines)

    # --- Сохранение ---
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return content


if __name__ == "__main__":
    from graph.models import Node, Edge, Snapshot
    from drift.detector import detect_drift
    from drift.scorer import score_all_events
    from drift.explainer import explain_all

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
    scored = score_all_events(events)
    cards = explain_all(scored)

    path = "reports/drift_report.md"
    generate_report(baseline, current, cards, output_path=path)
    print(f"Report saved to: {path}")
