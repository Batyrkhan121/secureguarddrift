# collector/envoy_parser.py
# Парсинг Envoy access логов (Istio/Linkerd)

import json
from datetime import datetime, timezone


def parse_envoy_log_line(line: str) -> dict | None:
    """Парсит одну строку Envoy access лога (JSON формат).

    Envoy формат (JSON):
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

    Returns:
        dict с полями: timestamp, source, destination, status_code, latency_ms, request_id
        или None если строка не распарсилась
    """
    try:
        log_entry = json.loads(line)
    except json.JSONDecodeError:
        return None

    # Извлечение полей
    timestamp_str = log_entry.get("start_time", "")
    response_code = log_entry.get("response_code", 0)
    duration_ms = log_entry.get("duration", 0)
    upstream_cluster = log_entry.get("upstream_cluster", "")
    downstream_addr = log_entry.get("downstream_remote_address", "")
    request_id = log_entry.get("request_id", "unknown")

    # Парсинг timestamp
    try:
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        timestamp = datetime.fromisoformat(timestamp_str)
    except (ValueError, AttributeError):
        timestamp = datetime.now(timezone.utc)

    # Извлечение destination из upstream_cluster
    # Формат: "outbound|8080||user-service.default.svc.cluster.local"
    destination = _extract_service_from_cluster(upstream_cluster)

    # Извлечение source из downstream_remote_address
    # Формат: "10.244.0.1:54321"
    source = _extract_source_from_downstream(downstream_addr)

    return {
        "timestamp": timestamp,
        "source": source,
        "destination": destination,
        "status_code": int(response_code),
        "latency_ms": float(duration_ms),
        "request_id": request_id,
    }


def _extract_service_from_cluster(cluster_name: str) -> str:
    """Извлекает имя сервиса из upstream_cluster.

    Примеры:
    - "outbound|8080||user-service.default.svc.cluster.local" -> "user-service"
    - "user-service" -> "user-service"
    """
    if not cluster_name:
        return "unknown"

    # Формат Istio: "outbound|8080||service.namespace.svc.cluster.local"
    if "||" in cluster_name:
        parts = cluster_name.split("||")
        if len(parts) >= 2:
            service_fqdn = parts[1]
            # Извлекаем имя сервиса: "user-service.default.svc.cluster.local" -> "user-service"
            return service_fqdn.split(".")[0]

    # Fallback: возвращаем как есть
    return cluster_name


def _extract_source_from_downstream(addr: str) -> str:
    """Извлекает IP из downstream_remote_address.

    Пример: "10.244.0.1:54321" -> "10.244.0.1"
    """
    if not addr:
        return "unknown"

    # Убираем порт
    if ":" in addr:
        return addr.split(":")[0]
    return addr


def parse_envoy_log_file(filepath: str) -> list[dict]:
    """Читает файл с Envoy логами (JSON lines), возвращает список записей.

    Returns:
        list[dict] с полями: timestamp, source, destination, status_code, latency_ms, request_id
    """
    records: list[dict] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = parse_envoy_log_line(line)
            if record:
                records.append(record)
    return records


if __name__ == "__main__":
    # Тестовая строка Envoy лога
    test_line = json.dumps({
        "start_time": "2026-02-10T10:15:30.123Z",
        "method": "GET",
        "path": "/api/users",
        "response_code": 200,
        "duration": 45,
        "upstream_cluster": "outbound|8080||user-service.default.svc.cluster.local",
        "downstream_remote_address": "10.244.0.1:54321",
        "request_id": "abc123-def456"
    })

    result = parse_envoy_log_line(test_line)
    if result:
        print("✅ Parsed Envoy log:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    else:
        print("❌ Failed to parse Envoy log")
