# Week 6: NetworkPolicy Generator

## Обзор

Неделя 6 добавляет автоматическую генерацию Kubernetes NetworkPolicy на основе drift-событий в режиме suggest-only.

## Архитектура

```
Drift Events → ExplainCard → Policy Generator → PolicySuggestion
                                    ↓
                            policy/storage.py (SQLite)
                                    ↓
                            API Routes (/api/policies)
                                    ↓
                            Dashboard UI (Policies Tab)
                                    ↓
                        Approve/Reject → kubectl apply
```

## Компоненты

### 1. Policy Templates (policy/templates.py)

Шаблоны Kubernetes NetworkPolicy:

```python
from policy.templates import deny_new_edge, restrict_to_gateway, deny_database_direct

# Блокировать новый edge
policy = deny_new_edge("order-svc", "payments-db")

# Разрешить только через gateway
policy = restrict_to_gateway("auth-svc", "api-gateway")

# Защита БД
policy = deny_database_direct("payments-db", ["payment-svc"])
```

### 2. Policy Generator (policy/generator.py)

Генерирует policies из ExplainCard:

```python
from policy.generator import generate_policies

policies = generate_policies(explain_cards)
# Возвращает list[PolicySuggestion]
```

**Правила генерации:**
- **new_edge + database_direct_access** → deny_database_direct
- **new_edge + bypass_gateway** → restrict_to_gateway
- **blast_radius_increase** → рекомендация
- Только для **critical** и **high** severity

### 3. Policy Renderer (policy/renderer.py)

Рендеринг в разные форматы:

```python
from policy.renderer import to_yaml, to_markdown, to_json, to_yaml_bundle

# Чистый YAML для kubectl
yaml_text = to_yaml(policy_suggestion)

# Markdown для отчета
md = to_markdown(policy_suggestion)

# JSON для API
json_text = to_json(policy_suggestion)

# Bundle всех policies
bundle = to_yaml_bundle(policy_suggestions)
```

### 4. Storage (policy/storage.py)

SQLite хранилище для policies:

```python
from policy.storage import PolicyStore

store = PolicyStore("data/policies.db")

# Сохранить
store.save_policy(policy_suggestion)

# Получить список
policies = store.list_policies(status="pending")

# Обновить статус
store.update_status(policy_id, "approved")
```

## API Endpoints

### GET /api/policies/

Список всех policies с фильтрацией:

```bash
curl http://localhost:8000/api/policies/?status=pending
```

Response:
```json
{
  "policies": [
    {
      "policy_id": "policy-deny-db-payments-db-order-svc",
      "severity": "critical",
      "risk_score": 85,
      "source": "order-svc",
      "destination": "payments-db",
      "status": "pending",
      "has_yaml": true
    }
  ],
  "count": 1
}
```

### GET /api/policies/{id}

Детали одной policy:

```bash
curl http://localhost:8000/api/policies/policy-deny-db-payments-db-order-svc
```

### GET /api/policies/{id}/yaml

Скачать YAML:

```bash
curl http://localhost:8000/api/policies/policy-deny-db-payments-db-order-svc/yaml \
  -o policy.yaml
```

### GET /api/policies/bundle/download

Скачать все policies в один YAML:

```bash
curl http://localhost:8000/api/policies/bundle/download?status=pending \
  -o policies-bundle.yaml
```

### POST /api/policies/{id}/approve

Одобрить policy:

```bash
curl -X POST http://localhost:8000/api/policies/policy-deny-db-payments-db-order-svc/approve
```

### POST /api/policies/{id}/reject

Отклонить policy:

```bash
curl -X POST http://localhost:8000/api/policies/policy-deny-db-payments-db-order-svc/reject
```

## Dashboard UI

### Вкладка "Policies"

Новая вкладка рядом с "Drift Feed":

- **Policy Cards**: показывают policy ID, risk score, source → destination
- **Status Badges**: pending (yellow), approved (green), rejected (red)
- **Actions**: Download YAML, Approve, Reject
- **Filter**: dropdown для фильтрации по статусу
- **Summary Bar**: показывает "X policies suggested"

### Использование

1. Перейти на вкладку "Policies"
2. Просмотреть предложенные policies
3. Нажать "Download YAML" для просмотра
4. Нажать "Approve" или "Reject"
5. Использовать "Download All YAML" для kubectl apply

## Workflow

### 1. Генерация Policies

```python
from drift.explainer import explain_all
from drift.scorer import score_all_events
from drift.detector import detect_drift
from policy.generator import generate_policies
from policy.storage import PolicyStore

# Детектим drift
events = detect_drift(baseline, current)

# Скорим и объясняем
scored = score_all_events(events)
cards = explain_all(scored)

# Генерируем policies
suggestions = generate_policies(cards)

# Сохраняем в БД
store = PolicyStore()
for suggestion in suggestions:
    store.save_policy(suggestion)
```

### 2. Review и Apply

```bash
# 1. Просмотр в Dashboard
# http://localhost:8000 → вкладка "Policies"

# 2. Скачать YAML
curl http://localhost:8000/api/policies/bundle/download?status=pending \
  -o policies.yaml

# 3. Просмотр
kubectl apply -f policies.yaml --dry-run=client

# 4. Применить
kubectl apply -f policies.yaml

# 5. Одобрить в UI или через API
curl -X POST http://localhost:8000/api/policies/{id}/approve
```

## Примеры Policy

### Deny Database Direct Access

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: restrict-payments-db-access
  namespace: default
  labels:
    app: secureguard-drift
    generated-by: drift-detector
    protected-resource: payments-db
spec:
  podSelector:
    matchLabels:
      app: payments-db
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: payment-svc
```

### Restrict to Gateway

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: restrict-auth-svc-to-api-gateway
  namespace: default
  labels:
    app: secureguard-drift
    generated-by: drift-detector
spec:
  podSelector:
    matchLabels:
      app: auth-svc
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway
```

## Тестирование

```bash
# Запуск тестов Week 6
pytest tests/test_week6_policies.py -v

# Проверка генерации
python policy/generator.py

# Проверка рендеринга
python policy/renderer.py
```

## Интеграция с Week 1-5

Week 6 использует:
- **Week 1-2**: drift detection, scoring
- **Week 3**: ExplainCard
- **Week 4**: API infrastructure
- **Week 5**: Real log collection

## Безопасность

- **Suggest-only режим**: policies НЕ применяются автоматически
- **Manual review**: требуется одобрение через UI/API
- **auto_apply_safe**: флаг для будущей автоматизации (сейчас всегда false)
- **RBAC**: требуется настройка в Kubernetes

## См. также

- [Week 1-5: Core functionality](../README.md)
- [API Reference](../docs/api-reference.md)
- [Kubernetes NetworkPolicy Docs](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
