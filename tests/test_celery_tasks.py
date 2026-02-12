# tests/test_celery_tasks.py
# Tests for Celery background tasks (without Redis/Celery broker)

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestCeleryAppConfig(unittest.TestCase):
    """Test Celery app configuration."""

    def test_celery_app_creation(self):
        from worker.app import celery_app
        self.assertEqual(celery_app.main, "secureguard")

    def test_celery_serializer_config(self):
        from worker.app import celery_app
        self.assertEqual(celery_app.conf.task_serializer, "json")
        self.assertIn("json", celery_app.conf.accept_content)
        self.assertEqual(celery_app.conf.timezone, "UTC")

    def test_celery_broker_url_default(self):
        from worker.app import broker_url
        self.assertIn("redis://", broker_url)

    def test_celery_includes_all_tasks(self):
        from worker.app import celery_app
        includes = celery_app.conf.get("include", [])
        self.assertIn("worker.tasks.snapshot", includes)
        self.assertIn("worker.tasks.drift", includes)
        self.assertIn("worker.tasks.notify", includes)


class TestBeatSchedule(unittest.TestCase):
    """Test Celery Beat schedule configuration."""

    def test_beat_schedule_defined(self):
        from worker.schedules import celery_app
        schedule = celery_app.conf.beat_schedule
        self.assertIn("build-hourly-snapshot", schedule)
        self.assertIn("cleanup-old-data", schedule)
        self.assertIn("update-baselines", schedule)

    def test_hourly_snapshot_schedule(self):
        from worker.schedules import celery_app
        entry = celery_app.conf.beat_schedule["build-hourly-snapshot"]
        self.assertEqual(entry["task"], "worker.tasks.snapshot.build_snapshot_task")

    def test_cleanup_schedule(self):
        from worker.schedules import celery_app
        entry = celery_app.conf.beat_schedule["cleanup-old-data"]
        self.assertEqual(entry["task"], "worker.tasks.drift.detect_drift_task")


class TestSnapshotTask(unittest.TestCase):
    """Test build_snapshot_task logic."""

    def test_task_is_registered(self):
        from worker.tasks.snapshot import build_snapshot_task
        self.assertTrue(build_snapshot_task.name.endswith("build_snapshot_task"))

    def test_task_max_retries(self):
        from worker.tasks.snapshot import build_snapshot_task
        self.assertEqual(build_snapshot_task.max_retries, 3)

    @patch("graph.storage.SnapshotStore")
    @patch("graph.builder.build_snapshot")
    @patch("collector.auto_detect.parse_log_file")
    def test_snapshot_task_success(self, mock_parse, mock_build, mock_store_cls):
        from worker.tasks.snapshot import build_snapshot_task

        mock_parse.return_value = [
            {"timestamp": "2026-01-01T10:00:00Z", "source": "a", "destination": "b",
             "status_code": 200, "latency_ms": 10},
        ]
        mock_snapshot = MagicMock()
        mock_snapshot.snapshot_id = "test-id"
        mock_snapshot.edges = [MagicMock()]
        mock_snapshot.nodes = [MagicMock(), MagicMock()]
        mock_build.return_value = mock_snapshot

        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        with patch("worker.tasks.drift.detect_drift_task") as mock_drift:
            mock_drift.delay = MagicMock()
            result = build_snapshot_task.apply(args=["tenant1", "/tmp/test.log"]).get()

        self.assertEqual(result["snapshot_id"], "test-id")
        self.assertEqual(result["edges"], 1)
        self.assertEqual(result["nodes"], 2)
        mock_store.save_snapshot.assert_called_once()

    @patch("collector.auto_detect.parse_log_file")
    def test_snapshot_task_empty_logs(self, mock_parse):
        from worker.tasks.snapshot import build_snapshot_task
        mock_parse.return_value = []
        result = build_snapshot_task.apply(args=["tenant1", "/tmp/empty.log"]).get()
        self.assertIsNone(result["snapshot_id"])
        self.assertEqual(result["status"], "empty")


class TestDriftTask(unittest.TestCase):
    """Test detect_drift_task logic."""

    def test_task_is_registered(self):
        from worker.tasks.drift import detect_drift_task
        self.assertTrue(detect_drift_task.name.endswith("detect_drift_task"))

    @patch("graph.storage.SnapshotStore")
    def test_drift_skipped_when_insufficient_snapshots(self, mock_store_cls):
        from worker.tasks.drift import detect_drift_task
        mock_store = MagicMock()
        mock_store.get_latest_two.return_value = None
        mock_store_cls.return_value = mock_store

        result = detect_drift_task.apply(args=["tenant1", "snap-1"]).get()
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["events"], 0)

    @patch("drift.explainer.explain_event")
    @patch("drift.scorer.score_all_events")
    @patch("drift.detector.detect_drift")
    @patch("graph.storage.SnapshotStore")
    def test_drift_detected(self, mock_store_cls, mock_detect, mock_score, mock_explain):
        from worker.tasks.drift import detect_drift_task

        mock_store = MagicMock()
        mock_store.get_latest_two.return_value = (MagicMock(), MagicMock())
        mock_store_cls.return_value = mock_store

        mock_event = MagicMock()
        mock_event.event_type = "new_edge"
        mock_event.source = "svc-a"
        mock_event.destination = "svc-b"
        mock_detect.return_value = [mock_event]
        mock_score.return_value = [(mock_event, 75, "high")]
        mock_explain.return_value = MagicMock()

        with patch("worker.tasks.notify.send_notifications_task") as mock_notify:
            mock_notify.delay = MagicMock()
            result = detect_drift_task.apply(args=["tenant1", "snap-1"]).get()

        self.assertEqual(result["status"], "detected")
        self.assertEqual(result["events"], 1)
        self.assertEqual(len(result["event_ids"]), 1)


class TestNotifyTask(unittest.TestCase):
    """Test send_notifications_task logic."""

    def test_task_is_registered(self):
        from worker.tasks.notify import send_notifications_task
        self.assertTrue(send_notifications_task.name.endswith("send_notifications_task"))

    def test_notify_sends_events(self):
        from worker.tasks.notify import send_notifications_task

        mock_settings = MagicMock()
        mock_router = MagicMock()
        mock_router.route_event.return_value = {"sent": ["slack"]}

        with patch.dict("sys.modules", {"integrations.config": MagicMock(IntegrationsSettings=lambda: mock_settings)}), \
             patch("integrations.router.NotificationRouter", return_value=mock_router):
            event_ids = ["tenant1:new_edge:svc-a:svc-b"]
            result = send_notifications_task.apply(args=["tenant1", event_ids]).get()

        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["sent"]), 1)

    def test_notify_empty_events(self):
        from worker.tasks.notify import send_notifications_task

        mock_settings = MagicMock()
        mock_router = MagicMock()

        with patch.dict("sys.modules", {"integrations.config": MagicMock(IntegrationsSettings=lambda: mock_settings)}), \
             patch("integrations.router.NotificationRouter", return_value=mock_router):
            result = send_notifications_task.apply(args=["tenant1", []]).get()

        self.assertEqual(result["total"], 0)


class TestDockerCompose(unittest.TestCase):
    """Test docker-compose.prod.yaml has worker and beat services."""

    def test_compose_has_worker_services(self):
        import yaml
        path = os.path.join(os.path.dirname(__file__), "..", "deploy", "docker-compose.prod.yaml")
        with open(path) as f:
            compose = yaml.safe_load(f)

        services = compose["services"]
        self.assertIn("worker", services)
        self.assertIn("beat", services)
        self.assertIn("celery", services["worker"]["command"])
        self.assertIn("celery", services["beat"]["command"])


if __name__ == "__main__":
    unittest.main()
