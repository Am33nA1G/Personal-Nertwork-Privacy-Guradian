"""Tests for the authenticated WebSocket endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from starlette.websockets import WebSocketDisconnect

from pnpg.config import DEFAULT_CONFIG


def _make_ws_app():
    from pnpg.api.routes.ws import router as ws_router
    from pnpg.ws.manager import WsManager

    app = FastAPI()
    app.state.config = dict(DEFAULT_CONFIG)
    app.state.config["jwt_secret"] = "test-secret-key-for-unit-tests"
    app.state.ws_manager = WsManager()
    app.include_router(ws_router, prefix="/api/v1")
    return app


def _make_token(secret: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "pnpg-user", "iat": now, "exp": now + timedelta(hours=1)},
        secret,
        algorithm="HS256",
    )


def test_ws_rejects_bad_token():
    app = _make_ws_app()

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect("/api/v1/ws/live?token=invalid") as websocket:
                websocket.receive_json()

    assert excinfo.value.code == 4001


def test_ws_accepts_valid_token():
    app = _make_ws_app()
    token = _make_token(app.state.config["jwt_secret"])

    with TestClient(app) as client:
        with client.websocket_connect(f"/api/v1/ws/live?token={token}"):
            pass
