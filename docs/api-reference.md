# API Reference — SecureGuardDrift

Base URL: `http://localhost:8000`

## Health

### `GET /health`
Проверка состояния сервиса.

**Response:**
```json
{"status": "ok"}
```

---

## Graph

### `GET /api/v1/graph/current`
Получить текущий (последний) снапшот графа.

**Response:** Snapshot object с nodes и edges.

### `GET /api/v1/graph/snapshots`
Список доступных снапшотов.

**Query params:**
- `limit` (int, default=50, max=200)

**Response:** Array of snapshot summaries.

### `GET /api/v1/graph/snapshots/{snapshot_id}`
Получить конкретный снапшот.

### `GET /api/v1/graph/diff`
Разница между двумя снапшотами.

**Query params:**
- `before` (string, required) — ID снапшота "до"
- `after` (string, required) — ID снапшота "после"

**Response:**
```json
{
  "added_nodes": ["service-c"],
  "removed_nodes": [],
  "added_edges": [{"source": "a", "target": "c"}],
  "removed_edges": []
}
```

---

## Drift

### `GET /api/v1/drift/latest`
Последний drift-анализ (сравнение двух последних снапшотов).

**Response:**
```json
{
  "snapshot_before": "abc123",
  "snapshot_after": "def456",
  "risk": {
    "total_score": 45.0,
    "risk_level": "high",
    "event_count": 3,
    "critical_count": 1,
    "events": [...]
  },
  "explanations": [...],
  "summary": "..."
}
```

### `GET /api/v1/drift/compare`
Сравнить два конкретных снапшота.

**Query params:**
- `before` (string, required)
- `after` (string, required)

### `GET /api/v1/drift/events`
Последние drift-события.

**Query params:**
- `limit` (int, default=20, max=100)

---

## Report

### `GET /api/v1/report/generate`
Сгенерировать отчёт.

**Query params:**
- `before` (string, optional) — ID снапшота "до"
- `after` (string, optional) — ID снапшота "после"
- `format` (string, default="json") — `json` или `markdown`

### `POST /api/v1/report/export`
Экспортировать пользовательский отчёт.

**Body:** JSON object с данными отчёта.
