"""Shared fixtures for Phase 5 API tests."""

import threading
import unittest.mock as mock
from pathlib import Path

import httpx
import pytest
from fastapi import Depends, FastAPI

from pnpg.config import DEFAULT_CONFIG
from pnpg.pipeline.detector import DetectorState


def _make_mock_db_pool():
    conn = mock.AsyncMock()
    acquire_cm = mock.AsyncMock()
    acquire_cm.__aenter__.return_value = conn
    acquire_cm.__aexit__.return_value = False

    pool = mock.MagicMock()
    pool.acquire.return_value = acquire_cm
    pool._conn = conn
    return pool


@pytest.fixture
def mock_db_pool():
    return _make_mock_db_pool()


@pytest.fixture
def test_config(tmp_path: Path):
    config = dict(DEFAULT_CONFIG)
    config["jwt_secret"] = "test-secret-key-for-unit-tests"
    config["auth_file"] = str(tmp_path / "auth.json")
    config["api_rate_limit"] = "100/minute"
    return config


@pytest.fixture
def app_with_state(mock_db_pool, test_config):
    from pnpg.api.auth import (
        get_current_user,
        hash_password,
        router as auth_router,
    )
    from pnpg.api.middleware import setup_rate_limiting

    app = FastAPI()
    setup_rate_limiting(app)

    app.state.db_pool = mock_db_pool
    app.state.config = test_config
    app.state.detector_state = DetectorState()
    app.state.password_hash = hash_password("testpass")
    app.state.needs_setup = False
    app.state.probe_type = "libpcap"
    app.state.drop_counter = [0]
    app.state.stop_event = threading.Event()
    app.state.started_at = 0.0

    app.include_router(auth_router, prefix="/api/v1")

    @app.get("/api/v1/status", dependencies=[Depends(get_current_user)])
    async def protected_status():
        return {"data": {"status": "ok"}}

    @app.get("/api/v1/health")
    async def public_health():
        db_status = "ok" if app.state.db_pool is not None else "unavailable"
        return {"data": {"status": "ok", "db": db_status}}

    return app


@pytest.fixture
async def client(app_with_state):
    transport = httpx.ASGITransport(app=app_with_state)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
        yield api


@pytest.fixture
async def auth_headers(client):
    response = await client.post("/api/v1/auth/login", json={"password": "testpass"})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_app_with_state(mock_db_pool, test_config):
    from pnpg.api.auth import hash_password, router as auth_router
    from pnpg.api.middleware import setup_rate_limiting
    from pnpg.api.routes.alerts import router as alerts_router
    from pnpg.api.routes.allowlist import router as allowlist_router
    from pnpg.api.routes.connections import router as connections_router
    from pnpg.api.routes.stats import router as stats_router
    from pnpg.api.routes.status import router as status_router

    app = FastAPI()
    setup_rate_limiting(app)

    app.state.db_pool = mock_db_pool
    app.state.config = test_config
    app.state.detector_state = DetectorState()
    app.state.password_hash = hash_password("testpass")
    app.state.needs_setup = False
    app.state.probe_type = "libpcap"
    app.state.drop_counter = [0]
    app.state.stop_event = threading.Event()
    app.state.started_at = 0.0
    app.state.ws_manager = None

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(connections_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(allowlist_router, prefix="/api/v1")
    app.include_router(stats_router, prefix="/api/v1")
    app.include_router(status_router, prefix="/api/v1")

    return app


@pytest.fixture
async def api_client(api_app_with_state):
    transport = httpx.ASGITransport(app=api_app_with_state)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
        yield api


@pytest.fixture
async def api_auth_headers(api_client):
    response = await api_client.post("/api/v1/auth/login", json={"password": "testpass"})
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
