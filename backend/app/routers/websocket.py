"""
WebSocket routes for real-time drift & alert streaming.

GET /ws/stream?model_id={id}

Subscribes to Redis pub/sub channels:
  - sentinel:drift:{model_id}:*     → drift events
  - sentinel:alerts:{model_id}      → alerts

Connection parameters:
  - token: JWT access token (query param or header)
  - heartbeat: server sends ping every 30s
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from jose import JWTError

from app.redis_client import get_redis
from app.services.auth_service import auth_service

logger = structlog.get_logger()

router = APIRouter()

# ── WebSocket connection manager ───────────────────────────────
class ConnectionManager:
    """Manages WebSocket connections and pub/sub subscriptions."""

    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, model_id: int):
        """Accept connection and track it."""
        await websocket.accept()
        if model_id not in self.active_connections:
            self.active_connections[model_id] = []
        self.active_connections[model_id].append(websocket)
        logger.info("websocket_connected", model_id=model_id)

    async def disconnect(self, websocket: WebSocket, model_id: int):
        """Remove connection from tracking."""
        if model_id in self.active_connections and websocket in self.active_connections[model_id]:
            self.active_connections[model_id].remove(websocket)
            if not self.active_connections[model_id]:
                del self.active_connections[model_id]
        logger.info("websocket_disconnected", model_id=model_id)

    async def broadcast_to_model(self, model_id: int, data: dict):
        """Broadcast message to all connections for a model."""
        if model_id not in self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections[model_id]:
            try:
                await connection.send_json(data)
            except Exception as exc:
                logger.warning("broadcast_failed", error=str(exc))
                disconnected.append(connection)

        for connection in disconnected:
            await self.disconnect(connection, model_id)


manager = ConnectionManager()


# ── WebSocket endpoint ─────────────────────────────────────────
@router.websocket("/ws/stream")
async def websocket_drift_stream(
    websocket: WebSocket,
    model_id: int = Query(..., gt=0),
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time drift & alert streaming.

    Client subscribes to a model's drift and alert events.
    Server sends heartbeat pings every 30 seconds.
    Requires a valid JWT access token as query parameter.

    Connection flow:
      1. Client connects with model_id and token
      2. Server validates JWT token
      3. Server accepts and subscribes to Redis channels
      4. Server forwards Redis messages to WebSocket
      5. Server sends heartbeat pings
      6. On disconnect, server unsubscribes and closes connection
    """
    # ── Validate JWT token ──────────────────────────────────
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        logger.warning("websocket_auth_missing", model_id=model_id)
        return

    try:
        user_id = auth_service.get_user_id_from_token(token)
    except (JWTError, Exception) as exc:
        await websocket.close(code=4001, reason="Invalid or expired token")
        logger.warning("websocket_auth_failed", model_id=model_id, error=str(exc))
        return

    logger.info("websocket_auth_success", model_id=model_id, user_id=user_id)
    await manager.connect(websocket, model_id)

    redis = await get_redis()
    pubsub = redis.pubsub()

    # Subscribe to drift channels (one per detector)
    drift_channels = [
        f"sentinel:drift:{model_id}:psi",
        f"sentinel:drift:{model_id}:ks_test",
        f"sentinel:drift:{model_id}:cusum",
        f"sentinel:drift:{model_id}:page_hinkley",
        f"sentinel:drift:{model_id}:isolation_forest",
        f"sentinel:drift:{model_id}:shap",
    ]

    # Subscribe to alerts channel
    alert_channel = f"sentinel:alerts:{model_id}"

    for channel in drift_channels + [alert_channel]:
        await pubsub.subscribe(channel)

    logger.info(
        "pubsub_subscribed",
        model_id=model_id,
        channels=drift_channels + [alert_channel],
    )

    # ── Background task: Redis message relay ──────────────────
    async def relay_redis_messages():
        """Listen to Redis pub/sub and forward to WebSocket."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        payload = json.loads(message["data"])
                        # Add server-side timestamp
                        payload["timestamp_received"] = datetime.now(timezone.utc).isoformat()

                        await manager.broadcast_to_model(model_id, payload)
                    except Exception as exc:
                        logger.warning("relay_failed", error=str(exc))
        except asyncio.CancelledError:
            logger.info("relay_task_cancelled", model_id=model_id)

    # ── Background task: Heartbeat ───────────────────────────
    async def send_heartbeat():
        """Send ping heartbeat every 30 seconds."""
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "model_id": model_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    raise
        except asyncio.CancelledError:
            logger.info("heartbeat_task_cancelled", model_id=model_id)
        except Exception as exc:
            logger.warning("heartbeat_failed", error=str(exc))

    relay_task = None
    heartbeat_task = None

    try:
        # Start background tasks
        relay_task = asyncio.create_task(relay_redis_messages())
        heartbeat_task = asyncio.create_task(send_heartbeat())

        # Listen for incoming messages from client
        while True:
            data = await websocket.receive_text()
            # Echo back (for testing keepalive)
            await websocket.send_json({
                "type": "echo",
                "message": data,
            })

    except WebSocketDisconnect:
        logger.info("websocket_disconnect", model_id=model_id, code=status.WS_1000_NORMAL_CLOSURE)

    except Exception as exc:
        logger.exception("websocket_error", model_id=model_id, error=str(exc))

    finally:
        # Clean up
        if relay_task:
            relay_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()

        await pubsub.unsubscribe(*drift_channels)
        await pubsub.unsubscribe(alert_channel)
        await pubsub.close()

        await manager.disconnect(websocket, model_id)

        logger.info("websocket_cleanup_complete", model_id=model_id)
