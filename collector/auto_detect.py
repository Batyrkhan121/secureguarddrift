# collector/auto_detect.py
# Автоматическое определение формата лога

import json


def detect_log_format(filepath: str, sample_lines: int = 5) -> str:
    """Определяет формат лога по первым строкам файла.

    Args:
        filepath: путь к файлу с логами
        sample_lines: количество строк для анализа (по умолчанию 5)

    Returns:
        "nginx" | "envoy" | "csv" | "unknown"
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = [f.readline().strip() for _ in range(sample_lines)]
            lines = [line for line in lines if line]  # Удаляем пустые
    except FileNotFoundError:
        return "unknown"

    if not lines:
        return "unknown"

    # Проверка на CSV (первая строка - заголовок)
    first_line = lines[0]
    if "," in first_line and any(
        header in first_line.lower()
        for header in ["timestamp", "source", "destination", "status"]
    ):
        return "csv"

    # Проверка на Envoy (JSON формат) - делаем раньше, чтобы избежать ложного срабатывания nginx
    json_count = 0
    for line in lines:
        try:
            obj = json.loads(line)
            # Проверяем наличие характерных полей Envoy
            if any(key in obj for key in ["upstream_cluster", "downstream_remote_address", "response_code"]):
                json_count += 1
        except json.JSONDecodeError:
            pass

    if json_count > 0:  # Хотя бы одна строка JSON с полями Envoy
        return "envoy"

    # Проверка на Nginx (текстовый формат с характерными паттернами)
    # Должны быть оба паттерна, чтобы отличить от JSON
    nginx_count = 0
    for line in lines:
        # Проверяем специфичные для nginx паттерны
        if " - - [" in line and "] \"" in line and ("HTTP/" in line or "GET " in line or "POST " in line):
            nginx_count += 1

    if nginx_count >= len(lines) // 2:  # Больше половины строк содержат nginx паттерны
        return "nginx"

    return "unknown"


def parse_log_file(filepath: str) -> list[dict]:
    """Автоматически определяет формат и парсит файл с логами.

    Returns:
        list[dict] с полями: timestamp, source, destination, status_code, latency_ms, request_id
    """
    log_format = detect_log_format(filepath)

    if log_format == "nginx":
        from collector.nginx_parser import parse_nginx_log_file
        return parse_nginx_log_file(filepath)

    elif log_format == "envoy":
        from collector.envoy_parser import parse_envoy_log_file
        return parse_envoy_log_file(filepath)

    elif log_format == "csv":
        from collector.ingress_parser import parse_log_file as parse_csv
        records = parse_csv(filepath)
        # Преобразуем к единому формату
        return [
            {
                "timestamp": r["timestamp"],
                "source": r["source"],
                "destination": r["destination"],
                "status_code": r["status_code"],
                "latency_ms": r["latency_ms"],
                "request_id": r.get("request_id", "unknown"),
            }
            for r in records
        ]

    else:
        raise ValueError(f"Unknown log format for file: {filepath}")


if __name__ == "__main__":
    # Тесты автоопределения
    import tempfile
    import os

    # Тест 1: CSV формат
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,source_service,destination_service,status_code,latency_ms\n")
        f.write("2026-02-10T10:00:00Z,api,user-svc,200,45.0\n")
        csv_file = f.name

    # Тест 2: Nginx формат
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write('10.0.0.1 - - [10/Feb/2026:10:15:30 +0000] "GET /api HTTP/1.1" 200 1234 "-" "-" 567 0.045 [default-user-service-8080] [-] 10.244.0.5:8080 890 0.042 200 abc123\n')
        nginx_file = f.name

    # Тест 3: Envoy формат
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write('{"start_time":"2026-02-10T10:15:30.123Z","response_code":200,"upstream_cluster":"outbound|8080||user-service","downstream_remote_address":"10.244.0.1:54321"}\n')
        envoy_file = f.name

    try:
        print(f"CSV format detected: {detect_log_format(csv_file)}")
        print(f"Nginx format detected: {detect_log_format(nginx_file)}")
        print(f"Envoy format detected: {detect_log_format(envoy_file)}")

        if detect_log_format(csv_file) == "csv":
            print("✅ CSV detection works")
        if detect_log_format(nginx_file) == "nginx":
            print("✅ Nginx detection works")
        if detect_log_format(envoy_file) == "envoy":
            print("✅ Envoy detection works")
    finally:
        os.unlink(csv_file)
        os.unlink(nginx_file)
        os.unlink(envoy_file)
