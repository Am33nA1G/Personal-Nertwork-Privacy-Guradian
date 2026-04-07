"""WebSocket live stream route."""

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt


logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket, token: str = Query(...)) -> None:
    """Authenticate and register a live websocket client."""
    config = websocket.app.state.config
    try:
        jwt.decode(token, config["jwt_secret"], algorithms=["HS256"])
    except (JWTError, Exception):  # noqa: BLE001
        await websocket.close(code=4001)
        return

    manager = websocket.app.state.ws_manager
    if manager is None:
        await websocket.close(code=1011)
        return

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "filter":
                manager.set_filter(websocket, data.get("data", {}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:  # noqa: BLE001
        manager.disconnect(websocket)
