# policy/templates.py
# Шаблоны Kubernetes NetworkPolicy

from dataclasses import dataclass, field


@dataclass
class NetworkPolicySpec:
    """Спецификация Kubernetes NetworkPolicy."""
    name: str
    namespace: str = "default"
    pod_selector: dict = field(default_factory=dict)
    ingress_rules: list[dict] = field(default_factory=list)
    egress_rules: list[dict] = field(default_factory=list)
    policy_types: list[str] = field(default_factory=lambda: ["Ingress"])


def deny_new_edge(source: str, destination: str, namespace: str = "default") -> dict:
    """Генерирует NetworkPolicy блокирующий новый edge source -> destination.

    Args:
        source: имя source сервиса
        destination: имя destination сервиса
        namespace: K8s namespace

    Returns:
        dict с полной спецификацией NetworkPolicy
    """
    policy_name = f"deny-{source}-to-{destination}".replace("_", "-")

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": policy_name,
            "namespace": namespace,
            "labels": {
                "app": "secureguard-drift",
                "generated-by": "drift-detector",
            },
        },
        "spec": {
            "podSelector": {
                "matchLabels": {"app": destination},
            },
            "policyTypes": ["Ingress"],
            "ingress": [
                {
                    "from": [
                        {
                            "podSelector": {
                                "matchLabels": {"app": "!=" + source},
                            }
                        }
                    ]
                }
            ],
        },
    }


def restrict_to_gateway(service: str, gateway: str = "api-gateway", namespace: str = "default") -> dict:
    """Генерирует NetworkPolicy разрешающий трафик только через gateway.

    Args:
        service: имя сервиса для защиты
        gateway: имя gateway (по умолчанию api-gateway)
        namespace: K8s namespace

    Returns:
        dict с полной спецификацией NetworkPolicy
    """
    policy_name = f"restrict-{service}-to-{gateway}".replace("_", "-")

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": policy_name,
            "namespace": namespace,
            "labels": {
                "app": "secureguard-drift",
                "generated-by": "drift-detector",
            },
        },
        "spec": {
            "podSelector": {
                "matchLabels": {"app": service},
            },
            "policyTypes": ["Ingress"],
            "ingress": [
                {
                    "from": [
                        {
                            "podSelector": {
                                "matchLabels": {"app": gateway},
                            }
                        }
                    ]
                }
            ],
        },
    }


def deny_database_direct(database: str, allowed_services: list[str], namespace: str = "default") -> dict:
    """Генерирует NetworkPolicy разрешающий доступ к БД только указанным сервисам.

    Args:
        database: имя БД сервиса (например, "payments-db")
        allowed_services: список сервисов с разрешенным доступом
        namespace: K8s namespace

    Returns:
        dict с полной спецификацией NetworkPolicy
    """
    policy_name = f"restrict-{database}-access".replace("_", "-")

    # Создаем список правил ingress для каждого разрешенного сервиса
    ingress_rules = []
    if allowed_services:
        for svc in allowed_services:
            ingress_rules.append({
                "from": [
                    {
                        "podSelector": {
                            "matchLabels": {"app": svc},
                        }
                    }
                ]
            })

    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": policy_name,
            "namespace": namespace,
            "labels": {
                "app": "secureguard-drift",
                "generated-by": "drift-detector",
                "protected-resource": database,
            },
        },
        "spec": {
            "podSelector": {
                "matchLabels": {"app": database},
            },
            "policyTypes": ["Ingress"],
            "ingress": ingress_rules,
        },
    }
