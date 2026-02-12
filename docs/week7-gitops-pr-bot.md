# Week 7: GitOps PR Bot

## Обзор

Неделя 7 добавляет автоматическое создание Pull Requests в GitOps репозиторий с NetworkPolicy YAML файлами на основе approved policies.

## Архитектура

```
Approved Policy → GitOps Bot → GitHub/GitLab API
                      ↓
              Create Branch → Commit YAML → Open PR
                      ↓
              SQLite (PR tracking) → Dashboard UI
```

## Компоненты

### 1. Конфигурация (gitops/config.py)

Использует pydantic-settings для управления настройками:

```python
from gitops.config import settings

print(f"Provider: {settings.provider}")  # "github" or "gitlab"
print(f"Enabled: {settings.enabled}")     # true/false
print(f"Repo: {settings.repo_owner}/{settings.repo_name}")
```

**Переменные окружения:**
```bash
GITOPS_ENABLED=true
GITOPS_PROVIDER=github
GITOPS_TOKEN=ghp_xxxxxxxxxxxx
GITOPS_API_URL=https://api.github.com
GITOPS_REPO_OWNER=my-org
GITOPS_REPO_NAME=gitops-repo
GITOPS_BASE_BRANCH=main
GITOPS_BRANCH_PREFIX=secureguard-policy-
GITOPS_POLICIES_PATH=kubernetes/network-policies
```

### 2. Git Clients

#### GitHub Client (gitops/github_client.py)

```python
from gitops.github_client import GitHubClient

client = GitHubClient(
    token="ghp_xxx",
    api_url="https://api.github.com",
    repo_owner="my-org",
    repo_name="gitops-repo"
)

# Создать ветку
client.create_branch("secureguard-policy-123", "main")

# Коммит файла
client.commit_file(
    "secureguard-policy-123",
    "kubernetes/network-policies/policy-123.yaml",
    yaml_content,
    "Add NetworkPolicy: policy-123"
)

# Создать PR
pr_info = client.create_pull_request(
    "secureguard-policy-123",
    "main",
    "feat: Add NetworkPolicy policy-123",
    "PR body with details..."
)

print(f"PR created: {pr_info.pr_url}")
```

#### GitLab Client (gitops/gitlab_client.py)

Аналогичный интерфейс для GitLab:

```python
from gitops.gitlab_client import GitLabClient

client = GitLabClient(
    token="glpat-xxx",
    api_url="https://gitlab.com/api/v4",
    repo_owner="my-group",
    repo_name="gitops-repo"
)

# Методы аналогичны GitHub client
```

### 3. PR Bot Logic (gitops/pr_bot.py)

Основная логика для обработки policies:

```python
from gitops.pr_bot import GitOpsPRBot
from gitops.config import settings
from gitops.storage import GitOpsPRStore

pr_store = GitOpsPRStore("data/gitops_prs.db")
bot = GitOpsPRBot(settings, pr_store)

# Обработать одну policy
result = bot.process_policy(policy_suggestion)

if result["status"] == "created":
    print(f"PR created: {result['pr_url']}")
elif result["status"] == "exists":
    print(f"PR already exists: {result['pr_url']}")
```

### 4. PR Storage (gitops/storage.py)

SQLite хранилище для отслеживания PRs:

```python
from gitops.storage import GitOpsPRStore

store = GitOpsPRStore("data/gitops_prs.db")

# Сохранить PR
pr_id = store.save_pr(
    policy_id="policy-123",
    branch_name="secureguard-policy-123",
    pr_number=42,
    pr_url="https://github.com/org/repo/pull/42",
    provider="github"
)

# Получить PR по policy_id
pr = store.get_pr_by_policy("policy-123")
print(f"PR #{pr['pr_number']}: {pr['pr_url']}")

# Список всех PRs
all_prs = store.list_prs()
open_prs = store.list_prs(status="open")

# Обновить статус
store.update_pr_status(pr_id, "merged")
```

## API Endpoints

### GET /api/gitops/config

Возвращает текущую конфигурацию GitOps (без секретов):

```bash
curl http://localhost:8000/api/gitops/config
```

Response:
```json
{
  "enabled": true,
  "provider": "github",
  "repo": "my-org/gitops-repo",
  "base_branch": "main",
  "policies_path": "kubernetes/network-policies"
}
```

### POST /api/gitops/sync

Синхронизирует все approved policies в GitOps репозиторий:

```bash
curl -X POST http://localhost:8000/api/gitops/sync
```

Response:
```json
{
  "status": "completed",
  "results": [
    {
      "policy_id": "policy-deny-db-payments-db-order-svc",
      "status": "created",
      "pr_url": "https://github.com/org/repo/pull/42",
      "pr_number": 42,
      "branch_name": "secureguard-policy-deny-db-payments-db-order-svc"
    }
  ]
}
```

### GET /api/gitops/prs

Возвращает список созданных Pull Requests:

```bash
curl http://localhost:8000/api/gitops/prs?status=open
```

Response:
```json
{
  "prs": [
    {
      "pr_id": 1,
      "policy_id": "policy-123",
      "branch_name": "secureguard-policy-123",
      "pr_number": 42,
      "pr_url": "https://github.com/org/repo/pull/42",
      "status": "open",
      "provider": "github",
      "created_at": "2026-02-12T07:00:00",
      "updated_at": null
    }
  ],
  "count": 1
}
```

### POST /api/gitops/sync-statuses

Синхронизирует статусы открытых PRs с GitHub/GitLab:

```bash
curl -X POST http://localhost:8000/api/gitops/sync-statuses
```

Response:
```json
{
  "status": "completed",
  "updated": [
    {
      "pr_id": 1,
      "old_status": "open",
      "new_status": "merged"
    }
  ],
  "count": 1
}
```

## Workflow

### 1. Setup Configuration

Создайте `.env` файл:

```bash
cp .env.example .env
```

Заполните GitOps настройки:

```bash
GITOPS_ENABLED=true
GITOPS_PROVIDER=github
GITOPS_TOKEN=ghp_your_token_here
GITOPS_REPO_OWNER=your-org
GITOPS_REPO_NAME=gitops-repo
GITOPS_BASE_BRANCH=main
```

### 2. Approve Policies

В Dashboard UI перейдите на вкладку "Policies" и нажмите "Approve" на нужных policies.

### 3. Sync to GitOps

Вызовите API endpoint:

```bash
curl -X POST http://localhost:8000/api/gitops/sync
```

Или добавьте кнопку в Dashboard UI.

### 4. Review PRs

Bot создаст Pull Requests в вашем GitOps репозитории. Каждый PR будет содержать:
- Ветка: `secureguard-policy-{policy_id}`
- Файл: `kubernetes/network-policies/{policy_id}.yaml`
- Описание с risk score, severity, причиной

### 5. Merge PRs

После review в GitHub/GitLab, merge PRs. SecureGuard автоматически обновит статусы при вызове `/api/gitops/sync-statuses`.

## Тестирование

```bash
# Запуск тестов Week 7
pytest tests/test_week7_gitops.py -v

# Все тесты используют mocked API calls
# Нет реальных обращений к GitHub/GitLab
```

## Безопасность

- **API Token**: Хранится в environment variables, не в коде
- **Rate Limiting**: Учитывайте лимиты GitHub/GitLab API
- **Permissions**: Token должен иметь права на создание веток и PRs
- **Branch Protection**: Настройте branch protection rules в GitOps repo

## Интеграция с Week 1-6

Week 7 использует:
- **Week 6**: PolicySuggestion, PolicyStore, approved policies
- **Week 1-5**: Drift detection, scoring, ExplainCard

## Требования

- Python 3.11+
- requests>=2.31.0
- pydantic-settings>=2.0.0
- GitHub/GitLab API token с правами на repo

## См. также

- [Week 6: NetworkPolicy Generator](week6-networkpolicy-generator.md)
- [GitHub REST API](https://docs.github.com/en/rest)
- [GitLab API](https://docs.gitlab.com/ee/api/)
