# api/websocket.py
"""WebSocket endpoint for real-time drift events with tenant isolation."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from auth.jwt_handler import jwt_handler

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections per tenant."""

    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, tenant_id: str):
        await ws.accept()
        self.connections.setdefault(tenant_id, []).append(ws)
        logger.info("WebSocket connected: tenant=%s, total=%d",
                     tenant_id, len(self.connections[tenant_id]))

    def disconnect(self, ws: WebSocket, tenant_id: str):
        conns = self.connections.get(tenant_id, [])
        if ws in conns:
            conns.remove(ws)
        logger.info("WebSocket disconnected: tenant=%s", tenant_id)

    async def broadcast(self, tenant_id: str, data: dict):
        """Send event to all connections of a specific tenant."""
        dead: list[WebSocket] = []
        for ws in self.connections.get(tenant_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, tenant_id)

    @property
    def active_count(self) -> int:
        return sum(len(v) for v in self.connections.values())


manager = ConnectionManager()


@router.websocket("/ws/events")
async def events_ws(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for real-time drift events.

    Auth via JWT in query param (WebSocket doesn't support custom headers).
    Clients send "ping" to get "pong" (heartbeat every 30s recommended).
    """
    try:
        payload = jwt_handler.verify_token(token)
    except Exception:
        await websocket.close(code=4001)
        return

    tenant_id = payload.get("tenant_id", "default")
    await manager.connect(websocket, tenant_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, tenant_id)


async def redis_subscriber():
    """Background task: listen to Redis pub/sub and broadcast via WebSocket."""
    from cache.redis_client import get_redis

    redis = get_redis()
    if redis is None:
        logger.info("Redis not available — WebSocket pub/sub disabled")
        return

    try:
        pubsub = redis.pubsub()
        await pubsub.psubscribe("drift_events:*")
        logger.info("Redis pub/sub listener started for drift_events:*")

        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"]
                tenant_id = channel.split(":", 1)[1] if ":" in channel else "default"
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    data = {"raw": str(message["data"])}
                await manager.broadcast(tenant_id, data)
    except asyncio.CancelledError:
        logger.info("Redis pub/sub listener shutting down")
    except Exception:
        logger.warning("Redis pub/sub listener error", exc_info=True)
