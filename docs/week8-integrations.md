# Week 8: Integrations (Slack, Jira, SIEM)

## Обзор

Неделя 8 добавляет интеграции с инструментами команды: Slack, Jira, SIEM. Drift-события автоматически попадают в рабочие каналы.

## Архитектура

```
Drift Event → Notification Router → Rule Engine
                      ↓
              [Slack, Jira, SIEM]
                      ↓
           Rate Limiting + Deduplication
```

## Компоненты

### 1. Конфигурация (integrations/config.py)

Использует pydantic-settings для управления всеми интеграциями:

```python
from integrations.config import settings

# Slack
print(settings.slack_enabled)
print(settings.slack_webhook_url)
print(settings.slack_min_severity)  # "critical", "high", "medium", "low"

# Jira
print(settings.jira_url)
print(settings.jira_project_key)

# SIEM
print(settings.siem_transport)  # "syslog" or "webhook"

# Router rules
print(settings.router_critical_targets)  # "slack,jira"
```

### 2. Slack Integration

#### Slack Notifier (integrations/slack_notifier.py)

```python
from integrations.slack_notifier import SlackNotifier

notifier = SlackNotifier(
    webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    min_severity="high",
    rate_limit_seconds=60
)

# Send notification
success = notifier.send_notification(explain_card)
```

**Функциональность:**
- **Block Kit форматирование**: Severity badges, risk scores, ссылки
- **Severity фильтр**: Отправка только critical/high (настраивается)
- **Rate limiting**: Не чаще 1 сообщения в минуту на event_type

### 3. Jira Integration (integrations/jira_client.py)

```python
from integrations.jira_client import JiraClient

client = JiraClient(
    url="https://your-domain.atlassian.net",
    email="your-email@example.com",
    api_token="your_api_token",
    project_key="PROJ",
    issue_type="Task"
)

# Create issue
result = client.create_issue(explain_card)
print(f"Created: {result['issue_url']}")
```

**Функциональность:**
- **Автоматическое создание тикетов** из drift-событий
- **Поля**: summary, description (Jira Markdown), priority, labels
- **Дедупликация**: Не создавать тикет если уже есть открытый для того же edge
- **Priority mapping**: critical → Highest, high → High, etc.

### 4. SIEM Integration (integrations/siem_exporter.py)

```python
from integrations.siem_exporter import SIEMExporter

# Syslog transport
exporter = SIEMExporter(
    transport="syslog",
    syslog_host="siem.example.com",
    syslog_port=514,
    syslog_protocol="udp"  # or "tcp"
)

# Webhook transport
exporter = SIEMExporter(
    transport="webhook",
    webhook_url="https://siem.example.com/api/events"
)

# Export event
success = exporter.export_event(explain_card)
```

**Функциональность:**
- **CEF (Common Event Format)**: Стандартный формат для SIEM
- **Транспорт**: syslog (UDP/TCP) или HTTP webhook
- **Поля**: severity, source, destination, risk_score, event_type, timestamp

### 5. Notification Router (integrations/router.py)

Маршрутизирует события по правилам:

```python
from integrations.router import NotificationRouter
from integrations.config import settings

router = NotificationRouter(settings)

# Route event
result = router.route_event(explain_card)
print(f"Sent to: {result['sent']}")  # ["slack", "jira"]
```

**Правила по умолчанию:**
- **critical** → Slack + Jira
- **high** → Slack only
- **medium** → SIEM only
- **low** → (none)

Правила настраиваются через environment variables.

## API Endpoints

### GET /api/integrations

Возвращает список настроенных интеграций:

```bash
curl http://localhost:8000/api/integrations
```

Response:
```json
{
  "integrations": [
    {
      "provider": "slack",
      "enabled": true,
      "configured": true,
      "min_severity": "high"
    },
    {
      "provider": "jira",
      "enabled": true,
      "configured": true,
      "url": "https://your-domain.atlassian.net",
      "project_key": "PROJ"
    }
  ],
  "count": 2
}
```

### POST /api/integrations/slack/test

Тестирует Slack webhook:

```bash
curl -X POST http://localhost:8000/api/integrations/slack/test
```

### POST /api/integrations/jira/test

Тестирует Jira подключение:

```bash
curl -X POST http://localhost:8000/api/integrations/jira/test
```

### POST /api/integrations/siem/test

Тестирует SIEM экспорт (генерирует CEF sample):

```bash
curl -X POST http://localhost:8000/api/integrations/siem/test
```

## Конфигурация

### Environment Variables

```bash
# Slack
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_MIN_SEVERITY=high
SLACK_RATE_LIMIT_SECONDS=60

# Jira
JIRA_ENABLED=true
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECT_KEY=PROJ
JIRA_ISSUE_TYPE=Task

# SIEM
SIEM_ENABLED=true
SIEM_TRANSPORT=syslog
SIEM_SYSLOG_HOST=siem.example.com
SIEM_SYSLOG_PORT=514
SIEM_SYSLOG_PROTOCOL=udp
SIEM_WEBHOOK_URL=

# Router Rules
ROUTER_CRITICAL_TARGETS=slack,jira
ROUTER_HIGH_TARGETS=slack
ROUTER_MEDIUM_TARGETS=siem
ROUTER_LOW_TARGETS=
```

## Примеры использования

### 1. Автоматическая маршрутизация

```python
from drift.detector import detect_drift
from drift.explainer import explain_all
from integrations.router import NotificationRouter
from integrations.config import settings

# Detect drift
events = detect_drift(baseline, current)
cards = explain_all(events)

# Route notifications
router = NotificationRouter(settings)
for card in cards:
    result = router.route_event(card)
    print(f"Event {card.event_type}: sent to {result['sent']}")
```

### 2. Slack notification с Block Kit

Slack сообщение будет содержать:
- 🔴 **Severity badge** (critical = red, high = orange, etc.)
- **Risk Score**: числовой badge
- **What changed**: описание изменения
- **Why risk**: список рисков
- **Affected services**: затронутые сервисы
- **Recommendation**: рекомендация

### 3. Jira issue

Jira тикет будет содержать:
- **Summary**: card.title
- **Description**: Jira Markdown с секциями
- **Priority**: Highest/High/Medium/Low (из severity)
- **Labels**: secureguard-drift, severity-{level}, event-{type}

### 4. SIEM CEF format

```
CEF:0|SecureGuardDrift|ServiceMesh Security|0.1.0|new_edge|Test Event|10|src=svc1 dst=svc2 cs1=85 cs1Label=RiskScore cs2=critical cs2Label=Severity cs3=svc1,svc2 cs3Label=AffectedServices msg=Test change
```

## Тестирование

```bash
# Запуск всех тестов Week 8
pytest tests/test_week8_integrations.py -v

# Тесты с mock API calls:
# - Slack Block Kit форматирование
# - Jira issue creation
# - CEF format validation
# - Router правила
# - Deduplication
```

## Безопасность

- **API tokens** только из environment variables
- **Rate limiting** для предотвращения спама
- **Deduplication** для предотвращения дубликатов
- **Timeout** для всех HTTP requests (10-30 seconds)

## Интеграция с Week 1-7

Week 8 использует:
- **Week 1-5**: Drift detection, scoring, ExplainCard
- **Week 6**: PolicySuggestion (для "Apply Policy" button)
- **Week 7**: GitOps PR bot

## См. также

- [Slack API Documentation](https://api.slack.com/messaging/webhooks)
- [Jira REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/)
- [CEF Format Spec](https://www.microfocus.com/documentation/arcsight/arcsight-smartconnectors/)
