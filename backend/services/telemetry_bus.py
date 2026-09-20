"""
Real-time Telemetry Bus over WebSockets.

Maintains a set of connected WebSocket clients and broadcasts
JSON-serialised telemetry events to all of them.
Disconnected clients are removed gracefully.

Singleton instance `telemetry_bus` is exported at module bottom.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Set

import structlog
from fastapi import WebSocket
from starlette.websockets import WebSocketState

log = structlog.get_logger(__name__)


class TelemetryBus:
    """Pub-sub WebSocket hub for real-time compliance telemetry events."""

    def __init__(self) -> None:
        self._clients: Set[WebSocket] = set()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and register the client."""
        await websocket.accept()
        self._clients.add(websocket)
        log.info("telemetry_client_connected", total_clients=len(self._clients))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket client from the active set."""
        self._clients.discard(websocket)
        log.info("telemetry_client_disconnected", total_clients=len(self._clients))

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    async def broadcast(self, event: dict) -> None:
        """
        Serialise *event* to JSON and send it to every connected client.
        Clients that have disconnected are silently removed.
        """
        if not self._clients:
            return

        payload = json.dumps(event, ensure_ascii=False, default=str)
        dead_clients: Set[WebSocket] = set()

        for client in list(self._clients):
            try:
                if client.client_state == WebSocketState.CONNECTED:
                    await client.send_text(payload)
                else:
                    dead_clients.add(client)
            except Exception as exc:  # pragma: no cover
                log.warning("telemetry_send_failed", error=str(exc))
                dead_clients.add(client)

        for dc in dead_clients:
            self._clients.discard(dc)

        if dead_clients:
            log.debug(
                "telemetry_dead_clients_removed",
                removed=len(dead_clients),
                remaining=len(self._clients),
            )

    # ------------------------------------------------------------------
    # Convenience factory for telemetry event dicts
    # ------------------------------------------------------------------

    @staticmethod
    def make_event(
        event_type: str,
        module: int,
        severity: str,
        summary: str,
        data: dict | None = None,
    ) -> dict:
        """Return a well-formed telemetry event dict ready for broadcast."""
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "module": module,
            "severity": severity,
            "summary": summary,
            "data": data or {},
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

telemetry_bus = TelemetryBus()
