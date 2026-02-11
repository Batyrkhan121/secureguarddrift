# drift/scorer.py
# Итоговый risk score для каждого drift-события

from drift.detector import DriftEvent
from drift.rules import evaluate_rules

# Base score по event_type
BASE_SCORES: dict[str, int] = {
    "new_edge":               40,
    "removed_edge":           20,
    "error_spike":            35,
    "latency_spike":          25,
    "traffic_spike":          30,
    "blast_radius_increase":  35,
}


def _severity_label(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def score_event(event: DriftEvent) -> tuple[int, str]:
    """Считает risk score для одного DriftEvent.

    1. Base score по event_type
    2. + сумма severity_boost от сработавших правил
    3. Clamp [0, 100]
    4. Записывает severity обратно в event.severity

    Возвращает (score, severity_label).
    """
    base = BASE_SCORES.get(event.event_type, 10)
    rule_results = evaluate_rules(event)
    boost = sum(r.severity_boost for r in rule_results)
    score = min(base + boost, 100)
    label = _severity_label(score)
    event.severity = label
    return score, label


def score_all_events(
    events: list[DriftEvent],
) -> list[tuple[DriftEvent, int, str]]:
    """Оценивает все события, сортирует по score убыванию."""
    scored = []
    for ev in events:
        sc, lbl = score_event(ev)
        scored.append((ev, sc, lbl))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


if __name__ == "__main__":
    events = [
        DriftEvent(
            event_type="new_edge",
            source="order-svc",
            destination="payments-db",
            details={"description": "New edge order-svc -> payments-db"},
        ),
        DriftEvent(
            event_type="error_spike",
            source="order-svc",
            destination="inventory-svc",
            details={"baseline_value": 0.01, "current_value": 0.15, "change_factor": 15.0},
        ),
        DriftEvent(
            event_type="latency_spike",
            source="payment-svc",
            destination="payments-db",
            details={"baseline_value": 25, "current_value": 250, "change_factor": 10.0},
        ),
    ]

    scored = score_all_events(events)
    print(f"{'source -> destination':<35s} {'type':<26s} {'score':>5s}  {'severity'}")
    print("-" * 80)
    for ev, sc, lbl in scored:
        edge = f"{ev.source} -> {ev.destination}"
        print(f"{edge:<35s} {ev.event_type:<26s} {sc:>5d}  {lbl}")
