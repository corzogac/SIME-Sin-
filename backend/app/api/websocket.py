"""WebSocket endpoint for real-time flood alert broadcasting.

Clients connect to /ws/alerts and receive JSON messages whenever
new alerts are detected or risk levels change.
"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

ws_router = APIRouter()

# Connected clients
_clients: set[WebSocket] = set()


@ws_router.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time alert streaming."""
    await websocket.accept()
    _clients.add(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(_clients)}")

    try:
        # Send a welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Conectado a SIME alertas en tiempo real",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Keep connection alive, listening for client messages (e.g., pings)
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        _clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(_clients)}")
    except Exception as e:
        _clients.discard(websocket)
        logger.warning(f"WebSocket error: {e}")


async def broadcast_alert(alert_data: dict):
    """Broadcast an alert to all connected WebSocket clients."""
    if not _clients:
        return

    message = json.dumps({
        "type": "alert",
        "data": alert_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, default=str)

    disconnected = set()
    for client in _clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)

    _clients.difference_update(disconnected)
    if disconnected:
        logger.info(f"Removed {len(disconnected)} disconnected WebSocket clients")


async def broadcast_flood_update(zones_data: list[dict]):
    """Broadcast flood zone updates to all connected clients."""
    if not _clients:
        return

    message = json.dumps({
        "type": "flood_update",
        "data": zones_data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, default=str)

    disconnected = set()
    for client in _clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)

    _clients.difference_update(disconnected)
