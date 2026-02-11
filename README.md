# SecureGuard Drift

> Explainable Runtime Change Control для Kubernetes

## Что это

SecureGuard Drift строит граф сервисных зависимостей из ingress-логов и автоматически обнаруживает изменения между снапшотами.
Каждое drift-событие оценивается по уровню риска с объяснением причины и рекомендацией.
Результат — интерактивный дашборд и Markdown-отчёт, готовый для triage-процесса.
Продукт работает в режиме read-only и не вмешивается в работу кластера.

## Быстрый старт

### Docker
```bash
docker-compose -f deploy/docker-compose.yaml up --build
# Открыть http://localhost:8000
```

### Python
```bash
python scripts/run_demo.py
# Открыть http://localhost:8000
```

### Kubernetes
```bash
kubectl apply -f deploy/k8s/
kubectl port-forward -n secureguard-drift svc/secureguard-drift 8000:80
```

## Скриншот

> *TODO: добавить скриншот дашборда*

## Как работает

1. **Collect** — парсит ingress-логи, строит граф сервисов с метриками
2. **Detect** — сравнивает снапшоты, находит новые/удалённые связи и аномалии метрик
3. **Score & Explain** — оценивает риск каждого события и генерирует объяснение
4. **Report** — формирует отчёт с рекомендациями (Markdown / JSON)

## Архитектура

```
ingress logs → collector → graph builder → storage (SQLite)
                                              ↓
                           dashboard ← API ← drift detector → scorer → explainer
```

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/health` | Статус сервера |
| GET | `/api/snapshots` | Список снапшотов |
| GET | `/api/graph/latest` | Граф последнего снапшота |
| GET | `/api/graph/{id}` | Граф по ID снапшота |
| GET | `/api/drift/` | Drift-события (default: 2 последних) |
| GET | `/api/drift/summary` | Сводка по severity |
| GET | `/api/report/md` | Отчёт в Markdown |
| GET | `/api/report/json` | Отчёт в JSON |

## Стек

**Backend:** Python 3.11, FastAPI, SQLite
**Frontend:** Cytoscape.js, vanilla JS
**Deploy:** Docker, Kubernetes

## Структура проекта

```
secureguarddrift/
├── api/            # FastAPI сервер + роуты
├── collector/      # Парсинг ingress-логов
├── graph/          # Построение графа, модели, хранилище
├── drift/          # Детектор, скорер, объяснятор
├── dashboard/      # Веб-дашборд (HTML + JS)
├── deploy/         # Dockerfile, docker-compose, K8s
├── scripts/        # Генерация данных, демо-скрипт
├── tests/          # Unit + smoke тесты
└── docs/           # Pilot guide, feedback
```

## Тесты

```bash
python -m pytest tests/ -v
```

## Roadmap

- [x] v1: drift detection + explain + report
- [ ] v2: NetworkPolicy generation + GitOps PR bot
- [ ] v3: ML/GNN для снижения false positives

## Документация

- [Pilot Guide](docs/pilot-guide.md)
- [Pilot Feedback](docs/pilot-feedback.md)

## Лицензия

MIT
