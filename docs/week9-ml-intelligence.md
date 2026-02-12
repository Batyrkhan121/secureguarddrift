# Week 9: ML/Intelligence - Снижение False Positives

## Обзор

Week 9 добавляет ML-слой для более умного scoring и уменьшения ложных срабатываний. Система использует:
- **Baseline profiling** - профилирование нормального поведения edges
- **Anomaly detection** - Z-score анализ для выявления аномалий
- **Pattern recognition** - распознавание типовых паттернов (deployment, canary, etc.)
- **Smart scoring** - интеллектуальный scoring с ML модификаторами
- **Feedback loop** - обучение на основе user feedback
- **Whitelist** - управление списком разрешенных connections

## Архитектура

```
Historical Snapshots → Baseline Profiling → EdgeProfile (mean, std)
                              ↓
Current Edge → Anomaly Detection → Z-scores → Anomaly Score
                              ↓
Drift Events → Pattern Recognition → PatternResult
                              ↓
All Modifiers → Smart Scorer → Final Score (0-100)
                              ↓
User Feedback → Feedback Loop → Update Whitelist/Patterns
```

## Компоненты

### 1. Baseline Profiling (`ml/baseline.py`)

Строит профиль "нормального" поведения для каждого edge.

**EdgeProfile:**
```python
@dataclass
class EdgeProfile:
    edge_key: tuple[str, str]
    request_count_mean: float
    request_count_std: float
    error_rate_mean: float
    error_rate_std: float
    p99_latency_mean: float
    p99_latency_std: float
    sample_count: int
```

**Функции:**
- `build_baseline(snapshots, edge_key, window_size=24)` - строит baseline по последним N снапшотам
- `update_baseline(current_profile, new_edge, window_size=24)` - incremental update с EMA

**Пример:**
```python
from ml.baseline import build_baseline

snapshots = snapshot_store.list_snapshots(limit=24)
baseline = build_baseline(snapshots, ("svc-a", "svc-b"))

print(f"Request count: {baseline.request_count_mean:.1f} ± {baseline.request_count_std:.1f}")
print(f"Error rate: {baseline.error_rate_mean:.3f} ± {baseline.error_rate_std:.3f}")
```

### 2. Anomaly Detection (`ml/anomaly.py`)

Z-score anomaly detection для выявления отклонений от baseline.

**Формула:**
```
z = (current - mean) / std
anomaly_score = Σ(z_i * weight_i)  где только z_i > 0
```

**Веса:**
- `error_rate`: 2.0 (самый важный)
- `p99_latency`: 1.5
- `request_count`: 1.0

**Пороги:**
- `z > 3.0` → anomaly
- `z > 2.0` → suspicious
- `z < 2.0` → normal

**Функции:**
- `calculate_z_scores(current_edge, baseline)` → ZScores
- `calculate_anomaly_score(z_scores)` → float
- `is_anomaly(current_edge, baseline)` → (is_anomaly, label, score)
- `get_anomaly_modifier(anomaly_score, label)` → int (-20 до +20)

**Пример:**
```python
from ml.anomaly import is_anomaly

is_anom, label, score = is_anomaly(current_edge, baseline)
if is_anom:
    print(f"Anomaly detected: {label}, score: {score:.1f}")
```

### 3. Pattern Recognition (`ml/patterns.py`)

Распознает типовые паттерны drift events.

**Паттерны:**

1. **Deployment** - много new_edge одновременно
   - Условие: ≥3 new_edge events
   - Modifier: -30 (снижает severity)
   - Объяснение: "Deployment detected: N new edges"

2. **Canary** - один edge с малым трафиком
   - Условие: new_edge с request_count < 10
   - Modifier: -20
   - Объяснение: "Canary release detected"

3. **Error Cascade** - цепочка ошибок
   - Условие: ≥2 error_spike events
   - Modifier: +10 (повышает severity)
   - Объяснение: "Error cascade: N errors"

4. **Rollback** - edges исчезли
   - Условие: ≥2 removed_edge events
   - Modifier: -40
   - Объяснение: "Rollback detected"

**Функции:**
- `recognize_pattern(events, current_event)` → PatternResult

**Пример:**
```python
from ml.patterns import recognize_pattern

pattern = recognize_pattern(all_events, current_event)
print(f"Pattern: {pattern.pattern_type}")
print(f"Modifier: {pattern.score_modifier}")
```

### 4. Smart Scoring (`ml/smart_scorer.py`)

Интеллектуальный scoring с учетом всех ML модификаторов.

**Формула:**
```
final_score = clamp(
    base_score + anomaly_modifier + pattern_modifier + history_modifier,
    0, 100
)
```

**Модификаторы:**
- `anomaly`: -20 (normal), +10 (suspicious), +20 (anomaly)
- `pattern`: -40 до -20 (deployment/canary), +10 (error cascade)
- `history`: -40 (если edge был safe раньше)

**Функции:**
- `calculate_smart_score(event, all_events, baseline, current_edge, history_safe)` → (score, severity, breakdown)
- `score_all_events_smart(events, baselines, current_edges, history_safe_edges)` → list[(event, score, severity, breakdown)]

**Пример:**
```python
from ml.smart_scorer import score_all_events_smart

scored = score_all_events_smart(
    events,
    baselines={("svc-a", "svc-b"): baseline},
    current_edges={("svc-a", "svc-b"): edge},
    history_safe_edges={("old-svc", "old-db")}
)

for event, score, severity, breakdown in scored:
    print(f"{event.source} -> {event.destination}: {score} ({severity})")
    if "pattern" in breakdown["modifiers"]:
        print(f"  Pattern: {breakdown['modifiers']['pattern']['reason']}")
```

### 5. Feedback Loop (`ml/feedback.py`)

User feedback для обучения системы.

**Verdicts:**
- `true_positive` - правильное срабатывание
- `false_positive` - ложное срабатывание (modifier: -40)
- `expected` - ожидаемое поведение (modifier: -30, auto-whitelist)

**FeedbackStore:**
- `save_feedback(feedback)` - сохранить feedback
- `get_feedback_for_edge(edge_key, event_type)` - получить историю
- `calculate_feedback_modifier(edge_key, event_type, store)` → int

**Пример:**
```python
from ml.feedback import FeedbackRecord, FeedbackStore

store = FeedbackStore()

feedback = FeedbackRecord(
    feedback_id=None,
    event_id="evt-123",
    edge_key=("svc-a", "svc-b"),
    event_type="new_edge",
    verdict="false_positive",
    comment="Expected deployment",
    created_at=datetime.utcnow(),
)

store.save_feedback(feedback)
```

### 6. Whitelist Management (`ml/whitelist.py`)

Управление whitelist и suppress rules.

**WhitelistStore:**
- `add_to_whitelist(entry)` - добавить edge
- `is_whitelisted(edge_key)` → bool
- `remove_from_whitelist(edge_key)` → bool
- `list_whitelist()` → list[WhitelistEntry]
- `add_suppress_rule(rule)` - временное подавление

**Пример:**
```python
from ml.whitelist import WhitelistEntry, WhitelistStore

store = WhitelistStore()

entry = WhitelistEntry(
    entry_id=None,
    source="frontend",
    destination="cache-db",
    reason="Known safe connection",
    created_at=datetime.utcnow(),
)

store.add_to_whitelist(entry)

if store.is_whitelisted(("frontend", "cache-db")):
    print("Edge is whitelisted, skip drift detection")
```

## API Endpoints

### POST /api/feedback
Сохраняет user feedback на drift событие.

**Request:**
```json
{
  "event_id": "evt-123",
  "source": "svc-a",
  "destination": "svc-b",
  "event_type": "new_edge",
  "verdict": "false_positive",
  "comment": "Expected deployment",
  "user": "admin"
}
```

**Response:**
```json
{
  "feedback_id": 42,
  "status": "saved",
  "auto_whitelisted": false
}
```

### GET /api/whitelist
Возвращает список всех whitelisted edges.

**Response:**
```json
{
  "count": 5,
  "entries": [
    {
      "entry_id": 1,
      "source": "frontend",
      "destination": "cache-db",
      "reason": "Known safe connection",
      "created_by": "admin",
      "created_at": "2026-02-12T10:00:00"
    }
  ]
}
```

### POST /api/whitelist
Добавляет edge в whitelist.

**Request:**
```json
{
  "source": "frontend",
  "destination": "cache-db",
  "reason": "Known safe connection",
  "created_by": "admin"
}
```

### DELETE /api/whitelist/{source}/{destination}
Удаляет edge из whitelist.

### GET /api/baseline/{source}/{destination}
Возвращает baseline профиль для edge.

**Response:**
```json
{
  "edge_key": ["svc-a", "svc-b"],
  "request_count": {"mean": 100.5, "std": 10.2},
  "error_rate": {"mean": 0.02, "std": 0.005},
  "p99_latency": {"mean": 50.3, "std": 5.1},
  "sample_count": 24,
  "last_updated": "2026-02-12T10:00:00"
}
```

## Использование

### Пример 1: Полный цикл с ML

```python
from graph.storage import SnapshotStore
from ml.baseline import build_baseline
from ml.smart_scorer import score_all_events_smart
from ml.whitelist import WhitelistStore
from drift.detector import detect_drift

# Загружаем данные
store = SnapshotStore()
whitelist_store = WhitelistStore()

snapshots = store.list_snapshots(limit=25)
baseline_snap = snapshots[-2]
current_snap = snapshots[-1]

# Строим baselines
baselines = {}
for edge in current_snap.edges:
    baseline = build_baseline(snapshots[:-1], edge.edge_key())
    if baseline:
        baselines[edge.edge_key()] = baseline

# Детектим drift
events = detect_drift(baseline_snap, current_snap)

# Фильтруем whitelist
events = [e for e in events if not whitelist_store.is_whitelisted((e.source, e.destination))]

# Smart scoring
current_edges = {e.edge_key(): e for e in current_snap.edges}
scored = score_all_events_smart(events, baselines, current_edges)

# Выводим результаты
for event, score, severity, breakdown in scored:
    print(f"{event.source} -> {event.destination}")
    print(f"  Score: {score} ({severity})")
    for mod_name, mod_data in breakdown["modifiers"].items():
        print(f"  {mod_name}: {mod_data['value']} - {mod_data['reason']}")
```

### Пример 2: Обработка feedback

```python
from ml.feedback import FeedbackRecord, FeedbackStore

store = FeedbackStore()

# User отметил как false positive
feedback = FeedbackRecord(
    feedback_id=None,
    event_id="evt-123",
    edge_key=("svc-a", "svc-b"),
    event_type="new_edge",
    verdict="false_positive",
    comment="This is expected during deployment",
    created_at=datetime.utcnow(),
    user="admin"
)

store.save_feedback(feedback)

# В будущем для этого edge
modifier = calculate_feedback_modifier(("svc-a", "svc-b"), "new_edge", store)
# modifier = -40 (снизит risk score)
```

## Тестирование

Все 8 unit-тестов проходят успешно:

```bash
cd /home/runner/work/secureguarddrift/secureguarddrift
python -m pytest tests/test_week9_ml.py -v
```

**Тесты:**
1. `test_baseline_calculation` - расчет baseline
2. `test_z_score_anomaly_detection` - anomaly detection
3. `test_deployment_pattern_reduces_score` - deployment pattern
4. `test_canary_pattern_detection` - canary pattern
5. `test_feedback_false_positive_reduces_score` - feedback loop
6. `test_whitelist_edge_filtering` - whitelist фильтрация
7. `test_smart_scorer_integration` - интеграция всех модификаторов
8. `test_update_baseline_incremental` - incremental update

## Зависимости

- **numpy>=1.24.0** - для Z-score calculations

## Итоги

Week 9 добавляет интеллектуальный слой поверх базового drift detection:

✅ **Baseline profiling** - понимание нормального поведения  
✅ **Anomaly detection** - статистическое выявление аномалий  
✅ **Pattern recognition** - распознавание типовых ситуаций  
✅ **Smart scoring** - учет всех факторов в итоговом score  
✅ **Feedback loop** - обучение на основе user feedback  
✅ **Whitelist** - управление исключениями  

Это значительно снижает количество false positives и делает систему более точной!
