"""WebSocket Connection Manager and Multi-Worker Event Bus for Real-Time Communication.

Phase 17 production-grade real-time delivery:
- Maps authenticated user_id to active WebSocket instances across browser sessions/tabs.
- Multi-process / multi-worker safe: uses MongoDB `notification_events` shared event bus to
  route events across workers without in-memory lock dependencies or single-process limitations.
- Zero data loss: MongoDB notifications collection is the authoritative persistent store.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.database.collections import COLLECTION_NOTIFICATION_EVENTS
from app.utils.datetime import utc_now


class ConnectionManager:
    """Manages active WebSocket connections per user and coordinates multi-worker delivery."""

    def __init__(self):
        # Unique worker process identifier for cross-worker event filtering
        self.worker_id: str = f"worker-{uuid.uuid4().hex[:8]}"
        # Map user_id to set of active WebSocket instances on this worker
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Multi-worker listener background task
        self._listener_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._last_event_time: datetime = utc_now()

    async def connect(self, user_id: str, websocket: WebSocket, subprotocol: Optional[str] = None) -> None:
        """Accepts a WebSocket connection and registers it under user_id."""
        await websocket.accept(subprotocol=subprotocol)
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(
            f"[{self.worker_id}] WebSocket client connected for user {user_id}. "
            f"Active sessions on worker: {len(self.active_connections[user_id])}"
        )

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Removes a WebSocket connection when client disconnects."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            logger.info(f"[{self.worker_id}] WebSocket client disconnected for user {user_id}")

    async def close_user_connections(self, user_id: str, code: int = 1000, reason: str = "Session closed") -> None:
        """Closes and removes all active WebSocket connections for a user (e.g. upon logout)."""
        if user_id in self.active_connections:
            sockets = list(self.active_connections[user_id])
            for ws in sockets:
                try:
                    await ws.close(code=code, reason=reason)
                except Exception:
                    pass
            self.active_connections.pop(user_id, None)
            logger.info(f"[{self.worker_id}] Closed all active WebSocket sessions for user {user_id}")

    async def send_personal_message(self, user_id: str, message: dict) -> None:
        """Sends JSON payload to all active WebSocket connections of a specific user on this worker."""
        if user_id not in self.active_connections:
            return

        dead_sockets = set()
        connections = list(self.active_connections[user_id])
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as exc:
                logger.warning(f"[{self.worker_id}] Error pushing WebSocket message to user {user_id}: {exc}")
                dead_sockets.add(websocket)

        for dead in dead_sockets:
            self.disconnect(user_id, dead)

    async def broadcast(self, message: dict) -> None:
        """Broadcasts a JSON message to all connected WebSocket clients across all users on this worker."""
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(user_id, message)

    async def publish_event(
        self,
        db: Optional[AsyncIOMotorDatabase],
        user_id: str,
        event_name: str,
        payload: dict,
    ) -> None:
        """
        Publishes a real-time event:
        1. Immediately delivers to any local connections on this worker.
        2. Records event in MongoDB `notification_events` collection to propagate to other workers.
        """
        now = utc_now()
        # 1. Local delivery (zero latency for clients connected to this worker process)
        await self.send_personal_message(user_id, payload)

        # 2. Cross-worker propagation via shared MongoDB event bus
        if db is not None:
            try:
                event_doc = {
                    "event_id": f"EVT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
                    "event": event_name,
                    "recipient_user_id": user_id,
                    "user_id": user_id,
                    "source_worker_id": self.worker_id,
                    "payload": payload,
                    "created_at": now,
                }
                await db[COLLECTION_NOTIFICATION_EVENTS].insert_one(event_doc)
            except Exception as bus_err:
                logger.debug(f"[{self.worker_id}] Could not write to notification_events: {bus_err}")

    async def start_event_listener(self, db: AsyncIOMotorDatabase) -> None:
        """Starts background worker task polling MongoDB `notification_events` for cross-worker events."""
        if self._is_running:
            return
        self._is_running = True
        self._last_event_time = utc_now()
        self._listener_task = asyncio.create_task(self._poll_notification_events(db))
        logger.info(f"[{self.worker_id}] Notification event bus listener started.")

    async def stop_event_listener(self) -> None:
        """Stops the cross-worker listener background task cleanly."""
        self._is_running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        logger.info(f"[{self.worker_id}] Notification event bus listener stopped.")

    async def _poll_notification_events(self, db: AsyncIOMotorDatabase) -> None:
        """Polls MongoDB for events emitted by other worker processes."""
        while self._is_running:
            try:
                await asyncio.sleep(0.2)  # 200ms poll interval
                if not self.active_connections:
                    continue  # No local connections, skip queries

                current_poll = utc_now()
                active_users = list(self.active_connections.keys())
                query = {
                    "created_at": {"$gt": self._last_event_time},
                    "source_worker_id": {"$ne": self.worker_id},
                    "recipient_user_id": {"$in": active_users},
                }

                events_cursor = db[COLLECTION_NOTIFICATION_EVENTS].find(query).sort("created_at", 1)
                new_events = await events_cursor.to_list(length=100)

                for ev in new_events:
                    recip = ev.get("recipient_user_id") or ev.get("user_id")
                    payload = ev.get("payload", {})
                    if recip and recip in self.active_connections:
                        await self.send_personal_message(recip, payload)

                self._last_event_time = current_poll
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[{self.worker_id}] Notice in event bus loop: {e}")
                await asyncio.sleep(0.5)


# Global singleton instance for app-wide access
manager = ConnectionManager()
