"""
WebSocket Connection Manager for VoiceSraver.
Broadcasts real-time transcription results to connected clients.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger("VoiceSraver.WS")


class WSManager:
    """Manages WebSocket connections and broadcasts transcription events."""

    def __init__(self, max_connections: int = 50):
        self.active_connections: list[WebSocket] = []
        self.max_connections = max_connections

    async def connect(self, websocket: WebSocket) -> bool:
        """Accept a new WebSocket connection."""
        if len(self.active_connections) >= self.max_connections:
            await websocket.close(code=1013, reason="Max connections reached")
            return False
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WS client connected. Total: {len(self.active_connections)}")
        return True

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WS client disconnected. Total: {len(self.active_connections)}")

    async def broadcast_transcription(self, text: str, is_partial: bool = False):
        """Broadcast transcription result to all connected clients."""
        if not self.active_connections:
            return
        message = json.dumps({
            "type": "transcription",
            "text": text,
            "is_partial": is_partial,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await self._broadcast(message)

    async def broadcast_event(self, event_type: str, data: dict | None = None):
        """Broadcast a system event (joined, left, error, etc)."""
        if not self.active_connections:
            return
        message = json.dumps({
            "type": "event",
            "event": event_type,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await self._broadcast(message)

    async def _broadcast(self, message: str):
        """Send message to all connections, remove dead ones."""
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_text(message)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)
