# collector/ingress_parser.py
# Парсинг CSV ingress-логов (формат generate_mock_data.py)

import csv
from datetime import datetime, timedelta


def parse_log_file(filepath: str) -> list[dict]:
    """Читает CSV ingress-лог, возвращает список словарей.

    Каждый словарь:
        {"timestamp": datetime, "source": str, "destination": str,
         "method": str, "path": str, "status_code": int, "latency_ms": float}
    """
    records: list[dict] = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_raw = row["timestamp"]
            # Убираем trailing 'Z' и парсим ISO-формат
            if ts_raw.endswith("Z"):
                ts_raw = ts_raw[:-1]
            records.append({
                "timestamp": datetime.fromisoformat(ts_raw),
                "source": row["source_service"],
                "destination": row["destination_service"],
                "method": row["http_method"],
                "path": row["path"],
                "status_code": int(row["status_code"]),
                "latency_ms": float(row["latency_ms"]),
            })
    return records


def filter_by_time_window(
    records: list[dict],
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Возвращает записи в указанном временном окне [start, end)."""
    return [r for r in records if start <= r["timestamp"] < end]


def get_time_windows(
    records: list[dict],
    window_hours: int = 1,
) -> list[tuple[datetime, datetime]]:
    """Разбивает весь период на окна по window_hours часов.

    Возвращает список (start, end).
    """
    if not records:
        return []

    ts_min = min(r["timestamp"] for r in records)
    ts_max = max(r["timestamp"] for r in records)

    # Выравниваем начало вниз до целого часа
    start = ts_min.replace(minute=0, second=0, microsecond=0)
    delta = timedelta(hours=window_hours)

    windows: list[tuple[datetime, datetime]] = []
    while start <= ts_max:
        windows.append((start, start + delta))
        start += delta

    return windows


if __name__ == "__main__":
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else "data/mock_ingress.csv"
    records = parse_log_file(filepath)
    print(f"Parsed {len(records)} records from {filepath}")
    windows = get_time_windows(records, window_hours=1)
    for i, (s, e) in enumerate(windows):
        chunk = filter_by_time_window(records, s, e)
        print(f"  Window {i}: {s} → {e}  ({len(chunk)} records)")
