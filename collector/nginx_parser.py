# collector/nginx_parser.py
# Парсинг nginx ingress controller access логов

import re
from datetime import datetime


def parse_nginx_log_line(line: str) -> dict | None:
    """Парсит одну строку nginx access лога.

    Формат nginx:
    $remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent
    "$http_referer" "$http_user_agent" $request_length $request_time
    [$proxy_upstream_name] [$proxy_alternative_upstream_name] $upstream_addr
    $upstream_response_length $upstream_response_time $upstream_status $req_id

    Returns:
        dict с полями: timestamp, source, destination, status_code, latency_ms, request_id
        или None если строка не распарсилась
    """
    # Регулярное выражение для парсинга nginx лога
    pattern = r"""
        ^(\S+)\s+-\s+\S+\s+                          # remote_addr - remote_user
        \[([^\]]+)\]\s+                               # [time_local]
        "(?:[^"]*?)"\s+                               # "request"
        (\d+)\s+\d+\s+                                # status body_bytes_sent
        "(?:[^"]*?)"\s+"(?:[^"]*?)"\s+                # "referer" "user_agent"
        \d+\s+(\d+\.?\d*)\s+                          # request_length request_time
        \[([^\]]*)\]\s+\[[^\]]*\]\s+                  # [proxy_upstream_name] [proxy_alternative]
        (\S+)\s+                                      # upstream_addr
        \S+\s+\S+\s+\S+\s+                            # upstream_response_length/time/status
        (\S+)                                         # req_id
    """

    match = re.search(pattern, line, re.VERBOSE)
    if not match:
        return None

    remote_addr = match.group(1)
    time_local = match.group(2)
    status_code = int(match.group(3))
    request_time = float(match.group(4))
    proxy_upstream = match.group(5)
    upstream_addr = match.group(6)
    req_id = match.group(7)

    # Парсинг времени: "10/Feb/2026:10:15:30 +0000"
    try:
        timestamp = datetime.strptime(time_local, "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        # Fallback без timezone
        timestamp = datetime.strptime(time_local.split()[0], "%d/%b/%Y:%H:%M:%S")

    # Извлечение destination из proxy_upstream_name: "default-user-service-8080"
    destination = _extract_service_from_upstream(proxy_upstream)

    # Source из upstream_addr или remote_addr
    source = _extract_service_from_addr(upstream_addr) or remote_addr

    return {
        "timestamp": timestamp,
        "source": source,
        "destination": destination,
        "status_code": status_code,
        "latency_ms": request_time * 1000,  # nginx дает в секундах
        "request_id": req_id,
    }


def _extract_service_from_upstream(upstream_name: str) -> str:
    """Извлекает имя сервиса из proxy_upstream_name.

    Пример: "default-user-service-8080" -> "user-service"
    """
    if not upstream_name or upstream_name == "-":
        return "unknown"

    # Убираем namespace и порт: "default-user-service-8080" -> "user-service"
    parts = upstream_name.split("-")
    if len(parts) >= 3:
        # Предполагаем формат: namespace-service-port
        return "-".join(parts[1:-1])
    return upstream_name


def _extract_service_from_addr(addr: str) -> str:
    """Извлекает имя сервиса из upstream_addr или возвращает IP.

    Пример: "10.244.0.5:8080" -> "10.244.0.5"
    """
    if not addr or addr == "-":
        return "unknown"

    # Убираем порт
    if ":" in addr:
        return addr.split(":")[0]
    return addr


def parse_nginx_log_file(filepath: str) -> list[dict]:
    """Читает файл с nginx логами, возвращает список записей.

    Returns:
        list[dict] с полями: timestamp, source, destination, status_code, latency_ms, request_id
    """
    records: list[dict] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = parse_nginx_log_line(line)
            if record:
                records.append(record)
    return records


if __name__ == "__main__":
    # Тестовая строка nginx лога
    test_line = (
        '10.0.0.1 - - [10/Feb/2026:10:15:30 +0000] "GET /api/users HTTP/1.1" 200 1234 '
        '"-" "Mozilla/5.0" 567 0.045 [default-user-service-8080] [-] 10.244.0.5:8080 '
        '890 0.042 200 abc123-def456'
    )

    result = parse_nginx_log_line(test_line)
    if result:
        print("✅ Parsed nginx log:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    else:
        print("❌ Failed to parse nginx log")
