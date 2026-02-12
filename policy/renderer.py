# policy/renderer.py
# Рендеринг PolicySuggestion в YAML/Markdown/JSON

import json
import yaml
from policy.generator import PolicySuggestion


def to_yaml(suggestion: PolicySuggestion) -> str:
    """Конвертирует PolicySuggestion в чистый K8s YAML.

    Args:
        suggestion: PolicySuggestion с policy_dict

    Returns:
        строка с YAML для kubectl apply
    """
    if not suggestion.yaml_dict:
        return "# Рекомендация без конкретной policy (требуется ручной аудит)\n"

    return yaml.dump(
        suggestion.yaml_dict,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def to_markdown(suggestion: PolicySuggestion) -> str:
    """Конвертирует PolicySuggestion в Markdown-блок с объяснением.

    Args:
        suggestion: PolicySuggestion

    Returns:
        строка Markdown для отчета
    """
    lines = [
        f"## NetworkPolicy: {suggestion.policy_id}",
        "",
        f"**Severity:** {suggestion.severity.upper()} (score: {suggestion.risk_score})",
        f"**Source:** {suggestion.source}",
        f"**Destination:** {suggestion.destination}",
        "",
        f"**Reason:**",
        suggestion.reason,
        "",
    ]

    if suggestion.yaml_dict:
        lines.append("**YAML:**")
        lines.append("```yaml")
        lines.append(to_yaml(suggestion).strip())
        lines.append("```")
    else:
        lines.append("_No specific policy template available. Manual audit required._")

    lines.append("")
    lines.append(f"**Auto-apply safe:** {'Yes' if suggestion.auto_apply_safe else 'No'}")
    lines.append("")

    return "\n".join(lines)


def to_json(suggestion: PolicySuggestion) -> str:
    """Конвертирует PolicySuggestion в JSON для API.

    Args:
        suggestion: PolicySuggestion

    Returns:
        строка JSON
    """
    data = {
        "policy_id": suggestion.policy_id,
        "severity": suggestion.severity,
        "risk_score": suggestion.risk_score,
        "source": suggestion.source,
        "destination": suggestion.destination,
        "reason": suggestion.reason,
        "auto_apply_safe": suggestion.auto_apply_safe,
        "yaml": to_yaml(suggestion) if suggestion.yaml_dict else None,
        "policy_spec": suggestion.yaml_dict if suggestion.yaml_dict else None,
    }

    return json.dumps(data, indent=2, ensure_ascii=False)


def to_yaml_bundle(suggestions: list[PolicySuggestion]) -> str:
    """Конвертирует список PolicySuggestion в один YAML файл с разделителями.

    Args:
        suggestions: список PolicySuggestion

    Returns:
        строка YAML с несколькими документами (--- разделители)
    """
    yamls = []
    for suggestion in suggestions:
        if suggestion.yaml_dict:
            yamls.append(to_yaml(suggestion).strip())

    return "\n---\n".join(yamls) + "\n"


if __name__ == "__main__":
    from policy.generator import PolicySuggestion
    from policy.templates import deny_database_direct

    # Тест рендера
    test_policy = deny_database_direct("payments-db", ["payment-svc"])
    suggestion = PolicySuggestion(
        policy_id="test-policy-1",
        yaml_dict=test_policy,
        reason="Тестовая причина",
        risk_score=85,
        severity="critical",
        auto_apply_safe=False,
        source="order-svc",
        destination="payments-db",
    )

    print("=== YAML ===")
    print(to_yaml(suggestion))

    print("\n=== Markdown ===")
    print(to_markdown(suggestion))

    print("\n=== JSON ===")
    print(to_json(suggestion))
