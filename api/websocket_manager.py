"""WebSocket connection manager for AutoPilot Dev.

Maintains a dict of active WebSocket connections keyed by ``session_id``.
All FastAPI routes and background tasks use the ``manager`` singleton
to push JSON updates to the connected browser client.
"""

from __future__ import annotations

import json
from typing import Dict

from fastapi import WebSocket

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Thread-safe (coroutine-safe) WebSocket connection registry."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept the WebSocket handshake and register the connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("WebSocket connected: session_id=%s  total=%d", session_id, len(self.active_connections))

    def disconnect(self, session_id: str) -> None:
        """Remove a connection from the registry (called on client disconnect)."""
        self.active_connections.pop(session_id, None)
        logger.info("WebSocket disconnected: session_id=%s  total=%d", session_id, len(self.active_connections))

    async def send_update(self, session_id: str, data: dict) -> None:
        """Send a JSON message to a specific client.

        Silently no-ops if the client is not connected (e.g. it disconnected
        before the background task finished).
        """
        ws = self.active_connections.get(session_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data, default=str))
            except Exception as exc:
                logger.warning(
                    "send_update failed for session_id=%s: %s", session_id, exc
                )
                self.disconnect(session_id)

    async def broadcast(self, data: dict) -> None:
        """Broadcast a JSON message to **all** connected clients."""
        payload = json.dumps(data, default=str)
        dead: list[str] = []
        for sid, ws in self.active_connections.items():
            try:
                await ws.send_text(payload)
            except Exception as exc:
                logger.warning("broadcast failed for session_id=%s: %s", sid, exc)
                dead.append(sid)
        for sid in dead:
            self.disconnect(sid)


# Singleton used across the whole application
manager = ConnectionManager()
