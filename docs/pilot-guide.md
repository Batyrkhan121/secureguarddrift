# SecureGuard Drift — Pilot Guide

## Обзор

SecureGuard Drift строит граф сервисных зависимостей из ingress-логов и обнаруживает аномальные изменения между снапшотами.
Каждое drift-событие оценивается по риску и сопровождается объяснением и рекомендацией.
Продукт работает в режиме **read-only** — не вмешивается в работу кластера и не меняет ресурсы.

## Требования

- Kubernetes 1.24+ (для пилота) или Docker (для демо)
- `kubectl` с доступом к кластеру
- Docker для сборки образа ИЛИ доступ к container registry
- Ingress-контроллер с логированием (nginx / envoy) ИЛИ OpenTelemetry (v2)

## Установка (5 минут)

### Вариант A: Docker (для демо)

```bash
cd deploy
docker-compose up --build
# Дашборд: http://localhost:8000
```

### Вариант B: Kubernetes (для пилота)

```bash
# Собрать образ
docker build -t secureguard-drift:latest -f deploy/Dockerfile .

# Применить манифесты
kubectl apply -f deploy/k8s/

# Дождаться готовности
kubectl wait --for=condition=ready pod -l app=secureguard-drift \
  -n secureguard-drift --timeout=60s

# Port-forward
kubectl port-forward -n secureguard-drift svc/secureguard-drift 8000:80
```

Или одной командой: `bash deploy/k8s/deploy.sh`

## Подключение к данным

### Вариант 1: Ingress-логи

1. Настройте экспорт логов nginx ingress controller в CSV/JSON
2. Формат: `timestamp, source, destination, method, path, status_code, latency_ms, bytes`
3. Укажите путь к логам в ConfigMap (`SECUREGUARD_DATA_DIR`)

### Вариант 2: OpenTelemetry (roadmap)

Планируется в v2 — приём трейсов через OTLP/HTTP.

## Что увидите

| Время | Результат |
|-------|-----------|
| 10 минут | Граф сервис → сервис с метриками |
| 1 час | Первые drift-события с оценкой риска |
| Конец дня | Полный отчёт со сводкой и рекомендациями |

## Дашборд

**URL:** `http://localhost:8000`

- **Граф** — интерактивная карта сервисов. Ноды раскрашены по типу (service / database / gateway). Рёбра с высоким error_rate подсвечены красным.
- **Drift Feed** — список событий справа, отсортирован по risk_score. Клик по карточке подсвечивает ребро в графе.
- **Export Report** — кнопка скачивает Markdown-отчёт.
- **Snapshot Selector** — выбор двух снапшотов для сравнения.

## Отчёт

- **Формат:** Markdown (`.md`) и JSON
- **Содержимое:** сводка по severity, таблица событий, рекомендации
- **Экспорт:** кнопка Export Report в дашборде или `GET /api/report/md`

## Безопасность

- Работает **read-only** — только читает логи
- Не создаёт и не меняет ресурсы в кластере
- Не требует cluster-admin (достаточно namespace-scoped RBAC)
- Данные хранятся локально в pod (SQLite в emptyDir)
- Не отправляет данные наружу

## Пилотный период (14 дней)

| Период | Активности |
|--------|-----------|
| День 1 | Установка, первые инсайты, проверка графа |
| Дни 2-3 | Накопление данных, появление drift-событий |
| Дни 4-14 | Анализ drift, регулярные отчёты, сбор фидбека |
| Финал | Итоговый отчёт + анкета обратной связи |

## Обратная связь

- **Анкета:** `[ссылка на форму]`
- **Контакт:** `pilot@secureguard.io`

## FAQ

**Может ли продукт что-то сломать?**
Нет. Работает в режиме read-only, не модифицирует ресурсы кластера.

**Сколько ресурсов потребляет?**
~128-256 MB RAM, минимум CPU (requests: 100m CPU, 128Mi RAM).

**Где хранятся данные?**
Внутри pod в emptyDir volume. Данные не покидают кластер.
