#!/usr/bin/env python3
# scripts/generate_mock_data.py
# Генератор фейковых ingress-логов (CSV)
#
# Формат: timestamp,source_service,destination_service,http_method,path,status_code,latency_ms
#
# Использование:
#   python scripts/generate_mock_data.py --output data/mock_ingress.csv --hours 3

import csv
import random
import argparse
import os
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Сервисы
# ---------------------------------------------------------------------------
SERVICES = [
    "api-gateway",
    "order-svc",
    "user-svc",
    "payment-svc",
    "inventory-svc",
    "notification-svc",
    "payments-db",
    "users-db",
    "orders-db",
]

# ---------------------------------------------------------------------------
# Нормальные связи: (source, target, method, path, base_latency_ms, error_rate)
# ---------------------------------------------------------------------------
NORMAL_EDGES = [
    ("api-gateway",   "order-svc",        "POST", "/api/orders",        35.0,  0.01),
    ("api-gateway",   "order-svc",        "GET",  "/api/orders",        25.0,  0.005),
    ("api-gateway",   "user-svc",         "GET",  "/api/users",         20.0,  0.005),
    ("api-gateway",   "user-svc",         "POST", "/api/users",         30.0,  0.01),
    ("order-svc",     "payment-svc",      "POST", "/internal/pay",      45.0,  0.01),
    ("order-svc",     "inventory-svc",    "GET",  "/internal/stock",    15.0,  0.01),
    ("order-svc",     "inventory-svc",    "POST", "/internal/reserve",  25.0,  0.01),
    ("order-svc",     "orders-db",        "POST", "/db/write",          10.0,  0.005),
    ("payment-svc",   "payments-db",      "POST", "/db/write",          20.0,  0.005),
    ("payment-svc",   "payments-db",      "GET",  "/db/read",           12.0,  0.003),
    ("payment-svc",   "notification-svc", "POST", "/notify/payment",    30.0,  0.01),
    ("user-svc",      "users-db",         "GET",  "/db/read",           10.0,  0.003),
    ("user-svc",      "users-db",         "POST", "/db/write",          15.0,  0.005),
]

# ---------------------------------------------------------------------------
# Аномальные связи (появляются только в третьем часе)
# ---------------------------------------------------------------------------
ANOMALY_NEW_EDGES = [
    # order-svc→payments-db — прямая связь, которой раньше не было
    ("order-svc",  "payments-db", "GET",  "/db/read",  18.0, 0.02),
    ("order-svc",  "payments-db", "POST", "/db/write", 22.0, 0.03),
    # user-svc→orders-db — подозрительная связь
    ("user-svc",   "orders-db",   "GET",  "/db/read",  14.0, 0.02),
]

CSV_HEADER = [
    "timestamp",
    "source_service",
    "destination_service",
    "http_method",
    "path",
    "status_code",
    "latency_ms",
]


def _latency(base_ms: float, jitter_pct: float = 0.3) -> float:
    """Случайная латентность вокруг базового значения."""
    lo = base_ms * (1.0 - jitter_pct)
    hi = base_ms * (1.0 + jitter_pct)
    return round(random.uniform(lo, hi), 2)


def _status_code(error_rate: float) -> int:
    """200/201 или 5xx с заданной вероятностью ошибки."""
    if random.random() < error_rate:
        return random.choice([500, 502, 503])
    return random.choice([200, 200, 200, 201])


def _is_anomaly_hour(current: datetime, start: datetime, total_hours: int) -> bool:
    """Проверяет, находимся ли мы в последнем часе генерации."""
    elapsed = (current - start).total_seconds() / 3600.0
    return elapsed >= (total_hours - 1)


def generate_rows(start: datetime, total_hours: int) -> list:
    """Генерация всех строк лога."""
    rows = []
    end = start + timedelta(hours=total_hours)
    anomaly_start = start + timedelta(hours=total_hours - 1)
    current = start

    while current < end:
        # Шаг 1-5 секунд
        current += timedelta(seconds=random.uniform(1.0, 5.0))
        if current >= end:
            break

        in_anomaly = current >= anomaly_start

        # --- Нормальные рёбра ---
        edge = random.choice(NORMAL_EDGES)
        src, dst, method, path, base_lat, base_err = edge

        # Аномалия: payment-svc→payments-db латентность x10
        if in_anomaly and src == "payment-svc" and dst == "payments-db":
            lat = _latency(200.0, jitter_pct=0.25)
        else:
            lat = _latency(base_lat)

        # Аномалия: order-svc→inventory-svc error rate 15%
        if in_anomaly and src == "order-svc" and dst == "inventory-svc":
            status = _status_code(0.15)
        else:
            status = _status_code(base_err)

        rows.append([
            current.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            src, dst, method, path, status, lat,
        ])

        # --- Аномальные новые рёбра (только в последнем часе) ---
        if in_anomaly and random.random() < 0.12:
            anom_edge = random.choice(ANOMALY_NEW_EDGES)
            a_src, a_dst, a_method, a_path, a_lat, a_err = anom_edge
            # Небольшой сдвиг по времени, чтобы не совпадал с основной записью
            a_ts = current + timedelta(milliseconds=random.randint(50, 500))
            rows.append([
                a_ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                a_src, a_dst, a_method, a_path,
                _status_code(a_err), _latency(a_lat),
            ])

    # Сортируем по timestamp
    rows.sort(key=lambda r: r[0])
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Генератор фейковых ingress-логов (CSV)"
    )
    parser.add_argument(
        "--output", type=str, default="data/mock_ingress.csv",
        help="Путь к выходному файлу (по умолчанию data/mock_ingress.csv)",
    )
    parser.add_argument(
        "--hours", type=int, default=3,
        help="Количество часов данных (по умолчанию 3)",
    )
    args = parser.parse_args()

    # Создаём директорию если нужно
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    start_time = datetime(2026, 2, 10, 10, 0, 0)
    print(f"Generating {args.hours}h of mock ingress logs...")
    print(f"  Start : {start_time.isoformat()}Z")
    print(f"  End   : {(start_time + timedelta(hours=args.hours)).isoformat()}Z")
    print(f"  Anomaly hour: {args.hours - 1} → {args.hours}")

    rows = generate_rows(start_time, args.hours)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)

    # Статистика
    total = len(rows)
    errors = sum(1 for r in rows if int(r[5]) >= 500)
    unique_edges = set()
    for r in rows:
        unique_edges.add((r[1], r[2]))

    print(f"\nDone! Wrote {total} rows to {args.output}")
    print(f"  Unique edges : {len(unique_edges)}")
    print(f"  Total errors : {errors} ({errors / total * 100:.1f}%)")
    print("  Edges:")
    for src, dst in sorted(unique_edges):
        count = sum(1 for r in rows if r[1] == src and r[2] == dst)
        errs = sum(1 for r in rows if r[1] == src and r[2] == dst and int(r[5]) >= 500)
        pct = errs / count * 100 if count else 0
        print(f"    {src:20s} → {dst:20s}  {count:5d} rows, {errs:3d} errors ({pct:.1f}%)")


if __name__ == "__main__":
    main()
