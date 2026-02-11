# Архитектура SecureGuardDrift

## Обзор

SecureGuardDrift — система обнаружения дрифта сервисных зависимостей. Анализирует трафик между микросервисами, строит граф зависимостей и детектирует изменения, которые могут указывать на проблемы безопасности.

## Компоненты

### 1. Collector
Сбор данных из двух источников:
- **Ingress Parser** — парсинг логов nginx/envoy ingress controller
- **OTEL Receiver** — приём OpenTelemetry трасс через OTLP/HTTP

### 2. Graph
Построение и хранение графа зависимостей:
- **Builder** — агрегация событий в граф (узлы + рёбра с метриками)
- **Storage** — хранение снапшотов (SQLite или файлы)
- **Models** — Node, Edge, Snapshot

### 3. Drift
Анализ изменений:
- **Detector** — сравнение двух снапшотов, выявление новых/удалённых связей и метрических аномалий
- **Scorer** — расчёт risk score на основе правил
- **Explainer** — генерация человекочитаемых объяснений
- **Rules** — правила: bypass gateway, sensitive service access, blast radius

### 4. API
FastAPI-сервер:
- `/api/v1/graph/*` — текущий граф, снапшоты, diff
- `/api/v1/drift/*` — drift-события, сравнение
- `/api/v1/report/*` — генерация и экспорт отчётов

### 5. Dashboard
SPA на vanilla JS + D3.js:
- Визуализация графа с force-directed layout
- Лента drift-событий
- Карточки с объяснениями и рекомендациями

## Поток данных

```
Ingress Logs / OTEL Traces
        │
        ▼
    Collector (parse & extract edges)
        │
        ▼
    Graph Builder (aggregate → snapshot)
        │
        ▼
    Storage (SQLite)
        │
        ▼
    Drift Detector (compare snapshots)
        │
        ▼
    Scorer + Explainer (risk + explanations)
        │
        ▼
    API → Dashboard
```

## Технологии

- **Python 3.11+**
- **FastAPI** — API-сервер
- **SQLite** — хранение снапшотов
- **D3.js** — визуализация графа
- **Docker / Kubernetes** — деплой
