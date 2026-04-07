"""WebSocket client manager with batching and heartbeats."""

import asyncio
import logging
import time
from collections import deque

from fastapi import WebSocket


logger = logging.getLogger(__name__)


class WsManager:
    """Track live websocket clients and batch outbound events."""

    def __init__(
        self,
        batch_interval: float = 0.5,
        max_batch: int = 100,
        heartbeat_interval: float = 10.0,
    ) -> None:
        self._clients: dict[WebSocket, dict] = {}
        self._interval = batch_interval
        self._max_batch = max_batch
        self._heartbeat_interval = heartbeat_interval
        self._batch_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket, filter_: dict | None = None) -> None:
        """Accept and register a websocket client."""
        await ws.accept()
        self._clients[ws] = {
            "filter": filter_ or {},
            "queue": deque(maxlen=self._max_batch),
        }
        logger.info("WS client connected (%d total)", len(self._clients))

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a websocket client if present."""
        self._clients.pop(ws, None)
        logger.info("WS client disconnected (%d remaining)", len(self._clients))

    def set_filter(self, ws: WebSocket, filter_: dict) -> None:
        """Update the filter applied to a connected client."""
        if ws in self._clients:
            self._clients[ws]["filter"] = filter_

    async def broadcast(self, payload: dict) -> None:
        """Queue a payload for every connected client, applying client filters."""
        for ws, state in list(self._clients.items()):
            client_payload = payload
            filter_ = state["filter"]
            if filter_:
                process_filter = filter_.get("process")
                if process_filter:
                    conns = payload.get("connections", [])
                    filtered_conns = [
                        conn
                        for conn in conns
                        if conn.get("process_name") == process_filter
                    ]
                    if not filtered_conns and not payload.get("alerts"):
                        continue
                    client_payload = {**payload, "connections": filtered_conns}
            state["queue"].append(client_payload)

    async def _flush_loop(self) -> None:
        """Flush queued batches to every connected client on a timer."""
        while True:
            await asyncio.sleep(self._interval)
            await self._flush_once()

    async def _heartbeat_loop(self) -> None:
        """Send heartbeats to connected clients on a timer."""
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await self._heartbeat_once()

    async def _flush_once(self) -> None:
        """Flush one batch cycle for all connected clients."""
        for ws, state in list(self._clients.items()):
            if not state["queue"]:
                continue
            batch = list(state["queue"])
            state["queue"].clear()
            try:
                await asyncio.wait_for(
                    ws.send_json({"type": "batch", "events": batch}),
                    timeout=0.4,
                )
            except Exception:  # noqa: BLE001
                logger.warning("WS client dropped (slow or disconnected)")
                self.disconnect(ws)

    async def _heartbeat_once(self) -> None:
        """Send one heartbeat cycle to all clients."""
        for ws in list(self._clients.keys()):
            try:
                await asyncio.wait_for(
                    ws.send_json({"type": "heartbeat", "ts": time.time()}),
                    timeout=1.0,
                )
            except Exception:  # noqa: BLE001
                self.disconnect(ws)

    async def start(self) -> None:
        """Start background batch and heartbeat tasks."""
        if self._batch_task is None or self._batch_task.done():
            self._batch_task = asyncio.create_task(
                self._flush_loop(), name="ws-batch-flush"
            )
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(), name="ws-heartbeat"
            )

    async def stop(self) -> None:
        """Stop background tasks and close all connected clients."""
        for task in (self._batch_task, self._heartbeat_task):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._batch_task = None
        self._heartbeat_task = None

        for ws in list(self._clients.keys()):
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
        self._clients.clear()

    @property
    def client_count(self) -> int:
        """Return the current number of connected clients."""
        return len(self._clients)
