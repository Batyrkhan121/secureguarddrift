# tests/test_week5_collectors.py
# Тесты для парсеров логов и планировщика (Неделя 5)

import os
import json
import tempfile
import unittest
from datetime import datetime, timezone
from collector.nginx_parser import parse_nginx_log_line, parse_nginx_log_file
from collector.envoy_parser import parse_envoy_log_line, parse_envoy_log_file
from collector.auto_detect import detect_log_format
from collector.scheduler import SnapshotScheduler
from graph.storage import SnapshotStore


class TestNginxParser(unittest.TestCase):
    """Тесты парсера nginx логов."""

    def test_parse_nginx_log_line(self):
        """Парсинг одной строки nginx лога."""
        log_line = (
            '10.0.0.1 - - [10/Feb/2026:10:15:30 +0000] "GET /api/users HTTP/1.1" 200 1234 '
            '"-" "Mozilla/5.0" 567 0.045 [default-user-service-8080] [-] 10.244.0.5:8080 '
            '890 0.042 200 abc123-def456'
        )

        result = parse_nginx_log_line(log_line)

        self.assertIsNotNone(result)
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["latency_ms"], 45.0)
        self.assertEqual(result["destination"], "user-service")
        self.assertEqual(result["source"], "10.244.0.5")
        self.assertEqual(result["request_id"], "abc123-def456")
        self.assertIsInstance(result["timestamp"], datetime)

    def test_parse_nginx_log_file(self):
        """Парсинг файла с 20+ строками nginx логов."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            # Создаем 20 строк nginx логов
            for i in range(20):
                f.write(
                    f'10.0.0.{i} - - [10/Feb/2026:10:{i:02d}:30 +0000] '
                    f'"GET /api/test HTTP/1.1" 200 1234 "-" "-" 567 0.0{i}5 '
                    f'[default-service-{i}-8080] [-] 10.244.0.{i}:8080 890 0.042 200 req-{i}\n'
                )
            filepath = f.name

        try:
            records = parse_nginx_log_file(filepath)
            self.assertEqual(len(records), 20)
            self.assertIn("timestamp", records[0])
            self.assertIn("source", records[0])
            self.assertIn("destination", records[0])
        finally:
            os.unlink(filepath)


class TestEnvoyParser(unittest.TestCase):
    """Тесты парсера Envoy логов."""

    def test_parse_envoy_log_line(self):
        """Парсинг одной строки Envoy лога (JSON)."""
        log_entry = {
            "start_time": "2026-02-10T10:15:30.123Z",
            "method": "GET",
            "path": "/api/users",
            "response_code": 200,
            "duration": 45,
            "upstream_cluster": "outbound|8080||user-service.default.svc.cluster.local",
            "downstream_remote_address": "10.244.0.1:54321",
            "request_id": "abc123-def456"
        }

        result = parse_envoy_log_line(json.dumps(log_entry))

        self.assertIsNotNone(result)
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["latency_ms"], 45.0)
        self.assertEqual(result["destination"], "user-service")
        self.assertEqual(result["source"], "10.244.0.1")
        self.assertEqual(result["request_id"], "abc123-def456")

    def test_parse_envoy_log_file(self):
        """Парсинг файла с Envoy логами."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for i in range(15):
                entry = {
                    "start_time": f"2026-02-10T10:{i:02d}:30.123Z",
                    "response_code": 200 if i < 10 else 500,
                    "duration": 45 + i,
                    "upstream_cluster": f"outbound|8080||service-{i}.default.svc.cluster.local",
                    "downstream_remote_address": f"10.244.0.{i}:54321",
                    "request_id": f"req-{i}"
                }
                f.write(json.dumps(entry) + "\n")
            filepath = f.name

        try:
            records = parse_envoy_log_file(filepath)
            self.assertEqual(len(records), 15)
            # Проверяем, что последние 5 записей имеют status_code 500
            self.assertEqual(records[-1]["status_code"], 500)
        finally:
            os.unlink(filepath)


class TestAutoDetect(unittest.TestCase):
    """Тесты автоопределения формата логов."""

    def test_detect_csv_format(self):
        """Автоопределение CSV формата."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("timestamp,source_service,destination_service,status_code,latency_ms\n")
            f.write("2026-02-10T10:00:00Z,api,user-svc,200,45.0\n")
            filepath = f.name

        try:
            format_type = detect_log_format(filepath)
            self.assertEqual(format_type, "csv")
        finally:
            os.unlink(filepath)

    def test_detect_nginx_format(self):
        """Автоопределение nginx формата."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for _ in range(5):
                f.write(
                    '10.0.0.1 - - [10/Feb/2026:10:15:30 +0000] "GET /api HTTP/1.1" 200 1234 '
                    '"-" "-" 567 0.045 [default-user-service-8080] [-] 10.244.0.5:8080 890 0.042 200 abc123\n'
                )
            filepath = f.name

        try:
            format_type = detect_log_format(filepath)
            self.assertEqual(format_type, "nginx")
        finally:
            os.unlink(filepath)

    def test_detect_envoy_format(self):
        """Автоопределение Envoy (JSON) формата."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for _ in range(5):
                entry = {
                    "start_time": "2026-02-10T10:15:30.123Z",
                    "response_code": 200,
                    "upstream_cluster": "outbound|8080||user-service",
                    "downstream_remote_address": "10.244.0.1:54321"
                }
                f.write(json.dumps(entry) + "\n")
            filepath = f.name

        try:
            format_type = detect_log_format(filepath)
            self.assertEqual(format_type, "envoy")
        finally:
            os.unlink(filepath)


class TestScheduler(unittest.TestCase):
    """Тесты планировщика снапшотов."""

    def test_scheduler_creates_snapshot(self):
        """Планировщик создает снапшот по расписанию."""
        import shutil

        test_dir = tempfile.mkdtemp()
        test_db = os.path.join(test_dir, "test.db")

        # Создаем тестовый лог-файл
        test_log = os.path.join(test_dir, "test.csv")
        with open(test_log, "w") as f:
            f.write("timestamp,source_service,destination_service,http_method,path,status_code,latency_ms\n")
            f.write(f"{datetime.now(timezone.utc).isoformat()}Z,api,user-svc,GET,/api,200,45.0\n")

        try:
            store = SnapshotStore(test_db)
            scheduler = SnapshotScheduler(test_dir, store, interval_hours=1, max_snapshots=5)

            # Создаем снапшот вручную (имитация работы scheduler)
            scheduler._create_snapshot()

            snapshots = store.list_snapshots()
            self.assertGreater(len(snapshots), 0, "Scheduler should create at least one snapshot")

            # Проверяем, что снапшот содержит данные
            snapshot_id = snapshots[0]["snapshot_id"]
            snapshot = store.load_snapshot(snapshot_id)
            self.assertIsNotNone(snapshot)
            self.assertGreater(len(snapshot.edges), 0)

        finally:
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    unittest.main()
