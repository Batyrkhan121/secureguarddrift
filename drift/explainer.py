# drift/explainer.py
# Генерация человекочитаемых объяснений для drift-событий

from dataclasses import dataclass
from drift.detector import DriftEvent
from drift.rules import evaluate_rules


@dataclass
class ExplainCard:
    """Карточка объяснения drift-события."""
    event_type: str
    title: str
    what_changed: str
    why_risk: list[str]
    affected: list[str]
    recommendation: str
    risk_score: int
    severity: str


# ---------------------------------------------------------------------------
# Генерация текстов
# ---------------------------------------------------------------------------

def _title(ev: DriftEvent) -> str:
    src, dst = ev.source, ev.destination
    return {
        "new_edge":               f"Новая связь: {src} -> {dst}",
        "removed_edge":           f"Исчезла связь: {src} -> {dst}",
        "error_spike":            f"Всплеск ошибок: {src} -> {dst}",
        "latency_spike":          f"Рост задержки: {src} -> {dst}",
        "traffic_spike":          f"Всплеск трафика: {src} -> {dst}",
        "blast_radius_increase":  f"Рост поверхности атаки: {src}",
    }.get(ev.event_type, f"Drift: {src} -> {dst}")


def _what_changed(ev: DriftEvent) -> str:
    d = ev.details
    src, dst = ev.source, ev.destination
    if ev.event_type == "new_edge":
        return (f"Появилась новая связь {src} -> {dst}, "
                "которой не было в предыдущем периоде")
    if ev.event_type == "removed_edge":
        return f"Связь {src} -> {dst} исчезла из текущего периода"
    if ev.event_type == "error_spike":
        bv = d.get("baseline_value", 0)
        cv = d.get("current_value", 0)
        cf = d.get("change_factor", 0)
        return f"Error rate вырос с {bv:.2%} до {cv:.2%} (рост в {cf}x)"
    if ev.event_type == "latency_spike":
        bv = d.get("baseline_value", 0)
        cv = d.get("current_value", 0)
        cf = d.get("change_factor", 0)
        return f"p99 latency вырос с {bv:.0f}ms до {cv:.0f}ms (рост в {cf}x)"
    if ev.event_type == "traffic_spike":
        bv = d.get("baseline_value", 0)
        cv = d.get("current_value", 0)
        cf = d.get("change_factor", 0)
        return f"Трафик вырос с {bv} до {cv} запросов (рост в {cf}x)"
    if ev.event_type == "blast_radius_increase":
        bv = d.get("baseline_value", 0)
        cv = d.get("current_value", 0)
        return (f"Количество исходящих связей {src} "
                f"выросло с {bv} до {cv}")
    return str(d)


def _recommendation(ev: DriftEvent) -> str:
    src, dst = ev.source, ev.destination
    if ev.event_type == "new_edge":
        if "-db" in dst:
            return (f"Проверить необходимость прямого доступа. "
                    f"Рассмотреть NetworkPolicy для блокировки {src} -> {dst}")
        return ("Проверить, является ли связь ожидаемой. "
                "Если нет — ограничить через NetworkPolicy")
    if ev.event_type == "error_spike":
        return (f"Проверить логи {dst}. "
                "Возможна деградация сервиса или некорректный деплой")
    if ev.event_type == "latency_spike":
        return (f"Проверить нагрузку на {dst}. "
                f"Рассмотреть rate-limiting для {src}")
    if ev.event_type == "removed_edge":
        return ("Проверить, ожидаемо ли исчезновение. "
                "Возможен сбой или изменение маршрутизации")
    if ev.event_type == "traffic_spike":
        return (f"Проверить источник роста трафика {src} -> {dst}. "
                f"Рассмотреть rate-limiting для {src}")
    if ev.event_type == "blast_radius_increase":
        return (f"Аудит новых исходящих связей {src}. "
                "Ограничить разрешённые направления")
    return "Требуется ручной анализ"


# ---------------------------------------------------------------------------
# Основные функции
# ---------------------------------------------------------------------------

def explain_event(event: DriftEvent, score: int, severity: str) -> ExplainCard:
    """Генерирует ExplainCard для одного drift-события."""
    rules = evaluate_rules(event)
    why = [r.reason for r in rules] if rules else [
        "Изменение зафиксировано, требует проверки"
    ]
    affected = [event.source]
    if event.destination != "*":
        affected.append(event.destination)

    return ExplainCard(
        event_type=event.event_type,
        title=_title(event),
        what_changed=_what_changed(event),
        why_risk=why,
        affected=affected,
        recommendation=_recommendation(event),
        risk_score=score,
        severity=severity,
    )


def explain_all(
    events_with_scores: list[tuple[DriftEvent, int, str]],
) -> list[ExplainCard]:
    """Генерирует ExplainCard для каждого события."""
    return [explain_event(ev, sc, sev) for ev, sc, sev in events_with_scores]


def format_card_text(card: ExplainCard) -> str:
    """Форматирует ExplainCard для вывода в консоль."""
    lines = [
        f"[{card.severity.upper():8s}] (score {card.risk_score:3d}) {card.title}",
        f"  Что:    {card.what_changed}",
    ]
    for reason in card.why_risk:
        lines.append(f"  Риск:   {reason}")
    lines.append(f"  Сервисы: {', '.join(card.affected)}")
    lines.append(f"  Совет:  {card.recommendation}")
    return "\n".join(lines)


if __name__ == "__main__":
    from drift.scorer import score_all_events

    events = [
        DriftEvent(event_type="new_edge", source="order-svc",
                   destination="payments-db",
                   details={"description": "New edge order-svc -> payments-db"}),
        DriftEvent(event_type="error_spike", source="order-svc",
                   destination="inventory-svc",
                   details={"baseline_value": 0.02, "current_value": 0.15,
                            "change_factor": 7.5}),
    ]

    scored = score_all_events(events)
    cards = explain_all(scored)
    for card in cards:
        print(format_card_text(card))
        print()
