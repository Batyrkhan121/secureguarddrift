# Week 5: Real Data Collection from Kubernetes

## Обзор

Неделя 5 добавляет возможность сбора реальных данных из Kubernetes кластера вместо мок-данных.

## Компоненты

### 1. Парсеры логов

#### nginx_parser.py
Парсит access логи nginx ingress controller.

```python
from collector.nginx_parser import parse_nginx_log_file

records = parse_nginx_log_file("/var/log/nginx/access.log")
# Возвращает list[dict] с полями:
# - timestamp: datetime
# - source: str (IP или имя сервиса)
# - destination: str (имя сервиса)
# - status_code: int
# - latency_ms: float
# - request_id: str
```

#### envoy_parser.py
Парсит JSON логи Envoy (Istio/Linkerd).

```python
from collector.envoy_parser import parse_envoy_log_file

records = parse_envoy_log_file("/var/log/envoy/access.log")
# Формат аналогичен nginx_parser
```

#### auto_detect.py
Автоматически определяет формат лога и вызывает нужный парсер.

```python
from collector.auto_detect import parse_log_file, detect_log_format

# Автоопределение формата
format_type = detect_log_format("/path/to/logs")  # "nginx" | "envoy" | "csv"

# Автоматический парсинг
records = parse_log_file("/path/to/logs")
```

### 2. Мониторинг и планирование

#### watcher.py
Следит за директорией с логами и обрабатывает новые файлы.

```python
from collector.watcher import LogWatcher

def on_new_file(filepath: str):
    print(f"New log file: {filepath}")
    # Обработка файла

watcher = LogWatcher("/var/log/ingress", on_new_file)
watcher.start()
# Обработать существующие файлы
watcher.process_existing_files()
```

#### scheduler.py
Автоматически создает снапшоты по расписанию.

```python
from collector.scheduler import SnapshotScheduler
from graph.storage import SnapshotStore

store = SnapshotStore("data/snapshots.db")
scheduler = SnapshotScheduler(
    log_dir="/var/log/ingress",
    storage=store,
    interval_hours=1,        # Снапшот каждый час
    max_snapshots=168        # Хранить 7 дней
)

scheduler.start()  # Запуск в фоновом потоке
```

### 3. Kubernetes Integration

#### collector-sidecar.yaml
DaemonSet с sidecar-контейнером для сбора логов.

```bash
# Деплой
kubectl apply -f deploy/k8s/collector-sidecar.yaml

# Проверка
kubectl get pods -n secureguard-drift
kubectl logs -n secureguard-drift <pod-name> -c secureguard-drift
```

**Архитектура:**
- DaemonSet размещается на нодах с ingress controller
- Sidecar копирует логи из `/var/log/nginx` в shared volume
- Основной контейнер читает из shared volume
- PersistentVolume для хранения данных

## Использование

### Локальный запуск с auto-detect

```python
from collector.auto_detect import parse_log_file
from graph.builder import build_snapshot
from graph.storage import SnapshotStore
from datetime import datetime, timedelta

# Парсинг логов (формат определяется автоматически)
records = parse_log_file("/var/log/ingress/access.log")

# Создание снапшота за последний час
end_time = datetime.now()
start_time = end_time - timedelta(hours=1)
snapshot = build_snapshot(records, start_time, end_time)

# Сохранение
store = SnapshotStore("data/snapshots.db")
store.save_snapshot(snapshot)
```

### Автоматический сбор с планировщиком

```python
from collector.scheduler import SnapshotScheduler
from collector.watcher import LogWatcher
from graph.storage import SnapshotStore

# Настройка хранилища
store = SnapshotStore("data/snapshots.db")

# Планировщик
scheduler = SnapshotScheduler(
    log_dir="/var/log/ingress",
    storage=store,
    interval_hours=1,
    max_snapshots=168
)
scheduler.start()

# Watcher для новых файлов
def process_log_file(filepath: str):
    print(f"Processing: {filepath}")
    # Файл будет обработан при следующем запуске scheduler

watcher = LogWatcher("/var/log/ingress", process_log_file)
watcher.start()
watcher.process_existing_files()

# Система работает в фоне
try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    watcher.stop()
    scheduler.stop()
```

## Тестирование

```bash
# Запуск тестов Week 5
pytest tests/test_week5_collectors.py -v

# Все тесты
pytest tests/ -v
```

## Форматы логов

### Nginx Access Log
```
10.0.0.1 - - [10/Feb/2026:10:15:30 +0000] "GET /api/users HTTP/1.1" 200 1234 
"-" "Mozilla/5.0" 567 0.045 [default-user-service-8080] [-] 10.244.0.5:8080 
890 0.042 200 abc123-def456
```

### Envoy JSON
```json
{
  "start_time": "2026-02-10T10:15:30.123Z",
  "method": "GET",
  "path": "/api/users",
  "response_code": 200,
  "duration": 45,
  "upstream_cluster": "outbound|8080||user-service.default.svc.cluster.local",
  "downstream_remote_address": "10.244.0.1:54321",
  "request_id": "abc123-def456"
}
```

### CSV (совместимость)
```csv
timestamp,source_service,destination_service,http_method,path,status_code,latency_ms
2026-02-10T10:00:00Z,api-gateway,user-service,GET,/api/users,200,45.0
```

## Требования

- Python 3.11+
- watchdog >= 3.0.0
- fastapi >= 0.104.0

## Архитектура

```
Kubernetes Cluster
    ↓
/var/log/nginx/ (host)
    ↓
Sidecar Container (log-copier)
    ↓
Shared Volume
    ↓
SecureGuard Container
    ↓
LogWatcher → auto_detect → nginx/envoy/csv parser
    ↓
SnapshotScheduler → build_snapshot → SnapshotStore
    ↓
SQLite Database
```

## См. также

- [Week 1-4: Базовая функциональность](../README.md)
- [API Reference](../docs/api-reference.md)
- [Deployment Guide](../docs/deployment.md)
