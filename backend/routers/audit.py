"""
Audit & Telemetry router.

Endpoints:
  GET       /api/v1/audit/logs    — Paginated audit log retrieval
  GET       /api/v1/audit/export  — Export full tamper-evident NDJSON bundle
  WebSocket /ws/telemetry         — Real-time telemetry event stream
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from models.schemas import AuditLogEntry, AuditLogsResponse
from services.audit_logger import audit_logger
from services.telemetry_bus import TelemetryBus, telemetry_bus

log = structlog.get_logger(__name__)

router = APIRouter(tags=["Audit & Telemetry"])
ws_router = APIRouter(tags=["WebSocket"])


# ---------------------------------------------------------------------------
# GET /audit/logs
# ---------------------------------------------------------------------------


@router.get(
    "/audit/logs",
    response_model=AuditLogsResponse,
    summary="Retrieve paginated audit log entries",
)
async def get_audit_logs(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=200, description="Entries per page"),
    event_type: Optional[str] = Query(
        default=None,
        description="Filter by event type (e.g. TRANSLATION, LEARN_QUERY)",
    ),
    module: Optional[str] = Query(
        default=None,
        description="Filter by module name (e.g. translate, learn, documents)",
    ),
    from_date: Optional[str] = Query(
        default=None,
        description="Filter entries on or after this date (YYYY-MM-DD)",
    ),
    to_date: Optional[str] = Query(
        default=None,
        description="Filter entries on or before this date (YYYY-MM-DD)",
    ),
) -> Any:
    """
    Returns paginated audit log entries from the append-only NDJSON store.
    Supports filtering by event_type, module, and date range.
    All PII in stored entries has already been masked at write time.
    """
    filters: Dict[str, Any] = {}
    if event_type:
        filters["event_type"] = event_type
    if module:
        filters["module"] = module
    if from_date:
        filters["from_date"] = from_date
    if to_date:
        filters["to_date"] = to_date

    result = await audit_logger.get_logs(page=page, page_size=page_size, filters=filters)

    # Coerce raw dict entries into AuditLogEntry models (fills missing optional fields)
    entries = []
    for raw in result.get("entries", []):
        entries.append(
            AuditLogEntry(
                audit_id=raw.get("audit_id", ""),
                timestamp=raw.get("timestamp", ""),
                event_type=raw.get("event_type", ""),
                module=raw.get("module", ""),
                status=raw.get("status", ""),
                uetr=raw.get("uetr"),
                message_type=raw.get("message_type"),
                details=raw.get("details", {}),
                hash=raw.get("hash", ""),
            )
        )

    return AuditLogsResponse(
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        entries=entries,
    )


# ---------------------------------------------------------------------------
# GET /audit/export
# ---------------------------------------------------------------------------


@router.get(
    "/audit/export",
    summary="Export full tamper-evident audit bundle as NDJSON",
)
async def export_audit_bundle() -> FileResponse:
    """
    Concatenates all daily audit NDJSON files into a single timestamped export bundle.
    Returns the bundle as a file download with tamper-evident SHA-256 hash chain.
    """
    bundle_path = await audit_logger.export_bundle()

    return FileResponse(
        path=bundle_path,
        media_type="application/x-ndjson",
        filename=bundle_path.split("/")[-1].split("\\")[-1],
        headers={
            "Content-Disposition": f"attachment; filename={bundle_path.split('/')[-1].split(chr(92))[-1]}",
            "X-Audit-Export": "tamper-evident-ndjson-bundle",
        },
    )


# ---------------------------------------------------------------------------
# WebSocket /ws/telemetry
# ---------------------------------------------------------------------------


@ws_router.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time telemetry event streaming.
    Clients receive JSON events whenever a translation, validation, or
    document operation completes.
    """
    await telemetry_bus.connect(websocket)
    log.info("telemetry_ws_connected", client=str(websocket.client))

    try:
        # Send initial connected event
        connected_event = TelemetryBus.make_event(
            event_type="CONNECTED",
            module=4,
            severity="INFO",
            summary="Telemetry stream connected successfully",
            data={"client": str(websocket.client)},
        )
        await websocket.send_json(connected_event)

        # Keep connection alive — client disconnects trigger WebSocketDisconnect
        while True:
            # Receive any client messages (ping/pong, keep-alive)
            try:
                data = await websocket.receive_text()
                log.debug("telemetry_ws_client_message", data=data[:100])
            except Exception:
                break

    except WebSocketDisconnect:
        log.info("telemetry_ws_disconnected", client=str(websocket.client))
    finally:
        await telemetry_bus.disconnect(websocket)
