# policy/generator.py
# Генератор NetworkPolicy на основе drift-событий

from dataclasses import dataclass
from drift.explainer import ExplainCard
from policy.templates import deny_new_edge, restrict_to_gateway, deny_database_direct


@dataclass
class PolicySuggestion:
    """Предложение NetworkPolicy для применения."""
    policy_id: str
    yaml_dict: dict
    reason: str
    risk_score: int
    severity: str
    auto_apply_safe: bool = False
    source: str = ""
    destination: str = ""


def generate_policies(cards: list[ExplainCard]) -> list[PolicySuggestion]:
    """Генерирует список PolicySuggestion на основе ExplainCard.

    Логика:
    - Для critical/high severity генерируем policies
    - new_edge + database_direct_access → deny_database_direct
    - new_edge + bypass_gateway → restrict_to_gateway
    - blast_radius_increase → deny лишних edges

    Args:
        cards: список ExplainCard с drift событиями

    Returns:
        список PolicySuggestion
    """
    suggestions = []

    for card in cards:
        # Только для critical и high severity
        if card.severity not in ("critical", "high"):
            continue

        # Извлекаем source и destination
        source = card.source
        destination = card.destination

        # Проверяем правила
        rules = card.rules_triggered if hasattr(card, "rules_triggered") else []

        # 1. new_edge + database_direct_access → deny_database_direct
        if card.event_type == "new_edge" and "database_direct_access" in rules:
            if destination.endswith("-db"):
                # Определяем владельца БД (для allow list)
                allowed_services = _get_database_owner(destination)

                policy_dict = deny_database_direct(destination, allowed_services)
                policy_id = f"policy-deny-db-{destination}-{source}"

                suggestions.append(PolicySuggestion(
                    policy_id=policy_id,
                    yaml_dict=policy_dict,
                    reason=f"Блокировка прямого доступа к {destination}. "
                           f"Обнаружено несанкционированное обращение от {source}.",
                    risk_score=card.risk_score,
                    severity=card.severity,
                    auto_apply_safe=False,  # БД критичны, требуют ручной проверки
                    source=source,
                    destination=destination,
                ))

        # 2. new_edge + bypass_gateway → restrict_to_gateway
        elif card.event_type == "new_edge" and "bypass_gateway" in rules:
            policy_dict = restrict_to_gateway(destination, "api-gateway")
            policy_id = f"policy-restrict-{destination}-to-gateway"

            suggestions.append(PolicySuggestion(
                policy_id=policy_id,
                yaml_dict=policy_dict,
                reason=f"Ограничение доступа к {destination} только через api-gateway. "
                       f"Обнаружен обход gateway от {source}.",
                risk_score=card.risk_score,
                severity=card.severity,
                auto_apply_safe=False,
                source=source,
                destination=destination,
            ))

        # 3. blast_radius_increase → deny новых edges
        elif card.event_type == "blast_radius_increase":
            # Для blast_radius генерируем общую рекомендацию
            # (конкретные edges неизвестны из этого события)
            policy_id = f"policy-limit-blast-{source}"
            reason = (f"Рост blast radius для {source}. "
                     f"Рекомендуется аудит всех исходящих соединений и "
                     f"ограничение через NetworkPolicy.")

            # Создаем "псевдо-policy" для рекомендации
            suggestions.append(PolicySuggestion(
                policy_id=policy_id,
                yaml_dict={},  # Пустой, т.к. это рекомендация
                reason=reason,
                risk_score=card.risk_score,
                severity=card.severity,
                auto_apply_safe=False,
                source=source,
                destination="*",
            ))

    return suggestions


def _get_database_owner(database_name: str) -> list[str]:
    """Возвращает список сервисов, которым разрешен доступ к БД.

    Args:
        database_name: имя БД (например, "payments-db")

    Returns:
        список имен сервисов
    """
    # Простая эвристика: "payments-db" → "payment-svc"
    db_to_service = {
        "payments-db": ["payment-svc"],
        "users-db": ["user-svc"],
        "orders-db": ["order-svc"],
        "inventory-db": ["inventory-svc"],
    }

    return db_to_service.get(database_name, [])


if __name__ == "__main__":
    # Тест генератора
    from drift.explainer import ExplainCard

    test_card = ExplainCard(
        event_type="new_edge",
        title="Новая связь: order-svc -> payments-db",
        what_changed="Появилась новая связь order-svc -> payments-db",
        why_risk=["Прямой доступ к БД минуя владельца"],
        affected=["order-svc", "payments-db"],
        recommendation="Блокировать прямой доступ",
        risk_score=85,
        severity="critical",
        source="order-svc",
        destination="payments-db",
        rules_triggered=["database_direct_access"],
    )

    policies = generate_policies([test_card])
    print(f"Generated {len(policies)} policy suggestion(s)")
    for p in policies:
        print(f"  - {p.policy_id}: {p.reason}")
