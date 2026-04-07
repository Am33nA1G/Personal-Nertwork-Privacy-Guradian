"""Tests for JWT auth and first-run setup."""

import json

import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    response = await client.post("/api/v1/auth/login", json={"password": "testpass"})

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    response = await client.post("/api/v1/auth/login", json={"password": "wrongpass"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_no_token(client):
    response = await client.get("/api/v1/status")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_valid_token(client, auth_headers):
    response = await client.get("/api/v1/status", headers=auth_headers)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_no_auth_required(client):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_setup_creates_auth_file(tmp_path, mock_db_pool, test_config):
    from fastapi import FastAPI

    from pnpg.api.auth import router as auth_router
    from pnpg.api.middleware import setup_rate_limiting

    app = FastAPI()
    setup_rate_limiting(app)
    app.state.db_pool = mock_db_pool
    app.state.config = test_config
    app.state.config["auth_file"] = str(tmp_path / "data" / "auth.json")
    app.state.detector_state = None
    app.state.password_hash = None
    app.state.needs_setup = True
    app.state.probe_type = "libpcap"
    app.state.drop_counter = [0]
    app.state.stop_event = None
    app.include_router(auth_router, prefix="/api/v1")

    async with pytest.importorskip("httpx").AsyncClient(
        transport=pytest.importorskip("httpx").ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/api/v1/auth/setup", json={"password": "newpass"})

    assert response.status_code == 200
    auth_file = tmp_path / "data" / "auth.json"
    assert auth_file.exists()
    assert "hash" in json.loads(auth_file.read_text(encoding="utf-8"))
