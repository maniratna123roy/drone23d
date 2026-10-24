"""WebSocket Manager for VantageCam real-time progress streaming.

Handles client connections, broadcasts stage updates, and manages subscriptions
per capture job.
"""

import json
import asyncio
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime


class VantageCamConnectionManager:
    """Manages WebSocket connections per capture job and broadcasts updates."""

    def __init__(self):
        # Dictionary: capture_id -> set of connected WebSocket clients
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, capture_id: str, websocket: WebSocket):
        """Register a new WebSocket connection for a capture."""
        await websocket.accept()

        if capture_id not in self.active_connections:
            self.active_connections[capture_id] = set()

        async with self._lock:
            self.active_connections[capture_id].add(websocket)

        print(f"[WS] Client connected to capture {capture_id}. Total: {len(self.active_connections[capture_id])}")

    async def disconnect(self, capture_id: str, websocket: WebSocket):
        """Unregister a WebSocket connection."""
        if capture_id in self.active_connections:
            async with self._lock:
                self.active_connections[capture_id].discard(websocket)

                # Clean up empty sets
                if not self.active_connections[capture_id]:
                    del self.active_connections[capture_id]

        print(f"[WS] Client disconnected from capture {capture_id}")

    async def broadcast_stage_start(
        self,
        capture_id: str,
        stage_index: int,
        stage_name: str,
    ):
        """Broadcast stage start event."""
        message = {
            "event": "stage_start",
            "capture_id": capture_id,
            "stage_index": stage_index,
            "stage_name": stage_name,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._broadcast(capture_id, message)

    async def broadcast_stage_progress(
        self,
        capture_id: str,
        stage_index: int,
        stage_name: str,
        progress_percent: float,
        metadata: Optional[dict] = None,
    ):
        """Broadcast stage progress update."""
        message = {
            "event": "stage_progress",
            "capture_id": capture_id,
            "stage_index": stage_index,
            "stage_name": stage_name,
            "progress_percent": min(100, max(0, progress_percent)),
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._broadcast(capture_id, message)

    async def broadcast_stage_complete(
        self,
        capture_id: str,
        stage_index: int,
        stage_name: str,
        duration_seconds: float,
        metrics: Optional[dict] = None,
    ):
        """Broadcast stage completion event."""
        message = {
            "event": "stage_complete",
            "capture_id": capture_id,
            "stage_index": stage_index,
            "stage_name": stage_name,
            "duration_seconds": duration_seconds,
            "metrics": metrics or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._broadcast(capture_id, message)

    async def broadcast_stage_error(
        self,
        capture_id: str,
        stage_index: int,
        stage_name: str,
        error_message: str,
    ):
        """Broadcast stage error event."""
        message = {
            "event": "stage_error",
            "capture_id": capture_id,
            "stage_index": stage_index,
            "stage_name": stage_name,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._broadcast(capture_id, message)

    async def broadcast_pipeline_complete(
        self,
        capture_id: str,
        total_duration_seconds: float,
        status: str,
        quality_verdict: Optional[str] = None,
        artifacts: Optional[list] = None,
    ):
        """Broadcast pipeline completion event."""
        message = {
            "event": "pipeline_complete",
            "capture_id": capture_id,
            "status": status,
            "total_duration_seconds": total_duration_seconds,
            "quality_verdict": quality_verdict,
            "artifacts": artifacts or [],
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._broadcast(capture_id, message)

    async def broadcast_pipeline_failed(
        self,
        capture_id: str,
        error_message: str,
        attempt: int,
        max_attempts: int,
    ):
        """Broadcast pipeline failure event."""
        message = {
            "event": "pipeline_failed",
            "capture_id": capture_id,
            "error_message": error_message,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "will_retry": attempt < max_attempts,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._broadcast(capture_id, message)

    async def broadcast_status_update(
        self,
        capture_id: str,
        status: str,
        progress_percent: float,
        current_stage: Optional[str] = None,
    ):
        """Broadcast overall capture status update."""
        message = {
            "event": "status_update",
            "capture_id": capture_id,
            "status": status,
            "progress_percent": min(100, max(0, progress_percent)),
            "current_stage": current_stage,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self._broadcast(capture_id, message)

    async def _broadcast(self, capture_id: str, message: dict):
        """Internal method to broadcast message to all connected clients."""
        if capture_id not in self.active_connections:
            return

        disconnected = set()
        async with self._lock:
            for websocket in self.active_connections[capture_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    print(f"[WS] Failed to send message to client: {str(e)}")
                    disconnected.add(websocket)

            # Remove disconnected clients
            for ws in disconnected:
                self.active_connections[capture_id].discard(ws)

    def get_connection_count(self, capture_id: str) -> int:
        """Get number of connected clients for a capture."""
        return len(self.active_connections.get(capture_id, set()))

    async def close_all_connections(self, capture_id: str, reason: str = "Server closing"):
        """Close all connections for a capture."""
        if capture_id not in self.active_connections:
            return

        async with self._lock:
            for websocket in list(self.active_connections[capture_id]):
                try:
                    await websocket.close(code=1000, reason=reason)
                except Exception as e:
                    print(f"[WS] Error closing websocket: {str(e)}")

            del self.active_connections[capture_id]

        print(f"[WS] Closed all connections for capture {capture_id}")


# Global manager instance
vantagecam_ws_manager = VantageCamConnectionManager()
