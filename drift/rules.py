# drift/rules.py
# Набор правил для оценки серьёзности drift-события

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dataclasses import dataclass
from drift.detector import DriftEvent

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------
SENSITIVE_SERVICES = ["payments-db", "users-db", "orders-db", "auth-svc"]
GATEWAY_SERVICES = ["api-gateway"]
DB_OWNER: dict[str, str] = {
    "payments-db": "payment-svc",
    "users-db":    "user-svc",
    "orders-db":   "order-svc",
}


@dataclass
class RuleResult:
    """Результат проверки одного правила."""
    rule_name: str
    triggered: bool
    reason: str
    severity_boost: int      # 0, 10, 20 или 30


# ---------------------------------------------------------------------------
# Правила
# ---------------------------------------------------------------------------

def rule_sensitive_target(event: DriftEvent) -> RuleResult:
    """Срабатывает если destination в SENSITIVE_SERVICES."""
    hit = event.destination in SENSITIVE_SERVICES
    return RuleResult(
        rule_name="sensitive_target",
        triggered=hit,
        reason=f"Связь направлена к чувствительному сервису {event.destination}" if hit else "",
        severity_boost=30 if hit else 0,
    )


def rule_bypass_gateway(event: DriftEvent) -> RuleResult:
    """Срабатывает если new_edge, source не gateway, и source не является
    «родным» сервисом для destination-БД."""
    if event.event_type != "new_edge":
        return RuleResult("bypass_gateway", False, "", 0)

    if event.source in GATEWAY_SERVICES:
        return RuleResult("bypass_gateway", False, "", 0)

    # Проверяем: source без "-svc" != destination без "-db"
    src_base = event.source.replace("-svc", "")
    dst_base = event.destination.replace("-db", "")
    hit = src_base != dst_base
    return RuleResult(
        rule_name="bypass_gateway",
        triggered=hit,
        reason="Прямая связь минуя API gateway" if hit else "",
        severity_boost=20 if hit else 0,
    )


def rule_database_direct_access(event: DriftEvent) -> RuleResult:
    """Срабатывает если destination — БД и source не ожидаемый сервис."""
    if "-db" not in event.destination:
        return RuleResult("database_direct_access", False, "", 0)

    expected = DB_OWNER.get(event.destination)
    hit = expected is not None and event.source != expected
    return RuleResult(
        rule_name="database_direct_access",
        triggered=hit,
        reason=(f"Прямой доступ к БД {event.destination} "
                f"от неожиданного сервиса {event.source}") if hit else "",
        severity_boost=30 if hit else 0,
    )


def rule_high_error_rate(event: DriftEvent) -> RuleResult:
    """Срабатывает если error_spike и current error_rate > 0.10."""
    if event.event_type != "error_spike":
        return RuleResult("high_error_rate", False, "", 0)

    cur = event.details.get("current_value", 0)
    hit = cur > 0.10
    return RuleResult(
        rule_name="high_error_rate",
        triggered=hit,
        reason="Уровень ошибок превышает 10%" if hit else "",
        severity_boost=20 if hit else 0,
    )


def rule_blast_radius(event: DriftEvent) -> RuleResult:
    """Срабатывает если event_type == blast_radius_increase."""
    hit = event.event_type == "blast_radius_increase"
    return RuleResult(
        rule_name="blast_radius",
        triggered=hit,
        reason=f"Поверхность атаки сервиса {event.source} увеличилась" if hit else "",
        severity_boost=15 if hit else 0,
    )


# ---------------------------------------------------------------------------
ALL_RULES = [
    rule_sensitive_target,
    rule_bypass_gateway,
    rule_database_direct_access,
    rule_high_error_rate,
    rule_blast_radius,
]


def evaluate_rules(event: DriftEvent) -> list[RuleResult]:
    """Прогоняет событие через все правила, возвращает только сработавшие."""
    return [r for fn in ALL_RULES if (r := fn(event)).triggered]


if __name__ == "__main__":
    ev = DriftEvent(
        event_type="new_edge",
        source="order-svc",
        destination="payments-db",
        details={"description": "New edge order-svc -> payments-db"},
    )
    results = evaluate_rules(ev)
    print(f"Event: {ev.event_type}  {ev.source} -> {ev.destination}")
    print(f"Triggered rules: {len(results)}")
    for r in results:
        print(f"  [{r.rule_name:24s}] boost=+{r.severity_boost}  {r.reason}")
