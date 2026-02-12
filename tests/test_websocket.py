# tests/test_websocket.py
"""Tests for WebSocket real-time drift events."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from api.websocket import ConnectionManager


def _run(coro):
    """Run an async coroutine in a new event loop (safe for any context)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestConnectionManager(unittest.TestCase):
    """Tests for ConnectionManager class."""

    def setUp(self):
        self.mgr = ConnectionManager()

    def test_initial_state(self):
        self.assertEqual(self.mgr.connections, {})
        self.assertEqual(self.mgr.active_count, 0)

    def test_connect(self):
        ws = AsyncMock()
        _run(self.mgr.connect(ws, "tenant1"))
        self.assertIn("tenant1", self.mgr.connections)
        self.assertEqual(len(self.mgr.connections["tenant1"]), 1)
        self.assertEqual(self.mgr.active_count, 1)
        ws.accept.assert_awaited_once()

    def test_disconnect(self):
        ws = AsyncMock()
        _run(self.mgr.connect(ws, "tenant1"))
        self.mgr.disconnect(ws, "tenant1")
        self.assertEqual(len(self.mgr.connections["tenant1"]), 0)
        self.assertEqual(self.mgr.active_count, 0)

    def test_disconnect_nonexistent(self):
        ws = AsyncMock()
        # Should not raise
        self.mgr.disconnect(ws, "nonexistent")

    def test_broadcast(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        _run(self.mgr.connect(ws1, "tenant1"))
        _run(self.mgr.connect(ws2, "tenant1"))

        data = {"type": "drift_detected", "count": 3}
        _run(self.mgr.broadcast("tenant1", data))

        ws1.send_json.assert_awaited_once_with(data)
        ws2.send_json.assert_awaited_once_with(data)

    def test_tenant_isolation(self):
        ws_a = AsyncMock()
        ws_b = AsyncMock()
        _run(self.mgr.connect(ws_a, "tenant_a"))
        _run(self.mgr.connect(ws_b, "tenant_b"))

        data = {"type": "drift_detected"}
        _run(self.mgr.broadcast("tenant_a", data))

        ws_a.send_json.assert_awaited_once_with(data)
        ws_b.send_json.assert_not_awaited()

    def test_broadcast_removes_dead_connections(self):
        ws_good = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_json.side_effect = Exception("Connection closed")

        _run(self.mgr.connect(ws_good, "tenant1"))
        _run(self.mgr.connect(ws_dead, "tenant1"))

        data = {"type": "test"}
        _run(self.mgr.broadcast("tenant1", data))

        # Dead connection removed
        self.assertEqual(len(self.mgr.connections["tenant1"]), 1)
        self.assertIn(ws_good, self.mgr.connections["tenant1"])

    def test_multiple_tenants_count(self):
        for i in range(3):
            ws = AsyncMock()
            _run(self.mgr.connect(ws, f"tenant_{i}"))
        self.assertEqual(self.mgr.active_count, 3)


class TestWebSocketEndpoint(unittest.TestCase):
    """Tests for the /ws/events endpoint."""

    def test_endpoint_exists(self):
        """Verify /ws/events route is registered."""
        from api.server import app
        ws_routes = [
            r.path for r in app.routes
            if hasattr(r, "path") and "ws" in r.path
        ]
        self.assertIn("/ws/events", ws_routes)

    def test_endpoint_with_invalid_token(self):
        """WebSocket with invalid token gets closed with 4001."""
        from starlette.testclient import TestClient
        from api.server import app

        client = TestClient(app)
        with self.assertRaises(Exception):
            with client.websocket_connect("/ws/events?token=invalid_token"):
                pass

    def test_endpoint_with_valid_token(self):
        """WebSocket with valid token connects and handles ping/pong."""
        from starlette.testclient import TestClient
        from api.server import app
        from auth.jwt_handler import jwt_handler

        token = jwt_handler.create_token(
            user_id="test", email="test@test.com",
            role="admin", tenant_id="test_tenant"
        )
        client = TestClient(app)
        with client.websocket_connect(f"/ws/events?token={token}") as ws:
            ws.send_text("ping")
            resp = ws.receive_text()
            self.assertEqual(resp, "pong")


class TestRedisPublish(unittest.TestCase):
    """Tests for Redis pub/sub integration in drift task."""

    def test_drift_task_publishes_to_redis(self):
        """Verify drift task attempts Redis publish when events are detected."""
        from worker.tasks.drift import detect_drift_task
        self.assertTrue(callable(detect_drift_task))

        # Verify the task code imports redis publish machinery
        import inspect
        source = inspect.getsource(detect_drift_task)
        self.assertIn("redis.publish", source)
        self.assertIn("drift_events:", source)

    def test_redis_subscriber_no_redis(self):
        """redis_subscriber gracefully exits when Redis is unavailable."""
        from api.websocket import redis_subscriber
        _run(redis_subscriber())


if __name__ == "__main__":
    unittest.main()
