"""Tests for /api/v1/threats, kill, and block-ip endpoints."""

import subprocess
import unittest.mock as mock

import pytest


# ---------------------------------------------------------------------------
# kill_process_windows and block_ip_windows_firewall unit tests
# ---------------------------------------------------------------------------


def test_kill_process_windows_success():
    from pnpg.api.routes.threats import kill_process_windows

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=0, stderr="")
        result = kill_process_windows(1234)

    assert result is True
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "taskkill" in args
    assert "1234" in args


def test_kill_process_windows_nonzero_return():
    from pnpg.api.routes.threats import kill_process_windows, RemediationError

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(
            returncode=1, stderr="Access is denied."
        )
        with pytest.raises(RemediationError, match="taskkill failed"):
            kill_process_windows(1234)


def test_kill_process_windows_timeout():
    from pnpg.api.routes.threats import kill_process_windows, RemediationError

    with mock.patch(
        "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="taskkill", timeout=10)
    ):
        with pytest.raises(RemediationError, match="taskkill timeout"):
            kill_process_windows(1234)


def test_block_ip_windows_firewall_success():
    from pnpg.api.routes.threats import block_ip_windows_firewall

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(returncode=0, stderr="")
        result = block_ip_windows_firewall("1.2.3.4")

    assert result is True
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "netsh" in cmd
    assert "1.2.3.4" in " ".join(cmd)


def test_block_ip_windows_firewall_nonzero_return():
    from pnpg.api.routes.threats import block_ip_windows_firewall, RemediationError

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.MagicMock(
            returncode=1, stderr="Access denied."
        )
        with pytest.raises(RemediationError, match="netsh firewall failed"):
            block_ip_windows_firewall("1.2.3.4")


def test_block_ip_windows_firewall_timeout():
    from pnpg.api.routes.threats import block_ip_windows_firewall, RemediationError

    with mock.patch(
        "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="netsh", timeout=10)
    ):
        with pytest.raises(RemediationError, match="netsh firewall timeout"):
            block_ip_windows_firewall("1.2.3.4")


# ---------------------------------------------------------------------------
# Helpers — extend api_app_with_state with threats router
# ---------------------------------------------------------------------------


@pytest.fixture
def threats_app(mock_db_pool, test_config):
    from fastapi import FastAPI

    from pnpg.api.auth import hash_password, router as auth_router
    from pnpg.api.middleware import setup_rate_limiting
    from pnpg.api.routes.threats import router as threats_router

    import threading

    app = FastAPI()
    setup_rate_limiting(app)

    app.state.db_pool = mock_db_pool
    app.state.config = test_config
    app.state.password_hash = hash_password("testpass")
    app.state.needs_setup = False
    app.state.probe_type = "libpcap"
    app.state.drop_counter = [0]
    app.state.stop_event = threading.Event()
    app.state.started_at = 0.0
    app.state.ws_manager = None
    app.state.detector_state = None

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(threats_router, prefix="/api/v1")

    return app


@pytest.fixture
async def threats_client(threats_app):
    import httpx

    transport = httpx.ASGITransport(app=threats_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def threats_auth_headers(threats_client):
    response = await threats_client.post(
        "/api/v1/auth/login", json={"password": "testpass"}
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /api/v1/threats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_threats_returns_paginated(
    threats_app, threats_client, threats_auth_headers
):
    conn = threats_app.state.db_pool._conn
    conn.fetchval.return_value = 1
    conn.fetch.return_value = [
        {
            "threat_id": "1",
            "status": "active",
            "severity": "HIGH",
            "process_name": "chrome.exe",
        }
    ]

    response = await threats_client.get(
        "/api/v1/threats", headers=threats_auth_headers
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 1
    assert payload["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_get_threats_db_unavailable(
    threats_app, threats_client, threats_auth_headers
):
    threats_app.state.db_pool = None

    response = await threats_client.get(
        "/api/v1/threats", headers=threats_auth_headers
    )

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# POST /api/v1/threats/{pid}/kill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kill_threat_process_success(
    threats_app, threats_client, threats_auth_headers
):
    conn = threats_app.state.db_pool._conn
    conn.fetchrow.return_value = {
        "threat_id": "11111111-1111-4111-8111-111111111111",
        "pid": 1234,
        "dst_ip": "93.184.216.34",
    }
    conn.execute.return_value = None

    with mock.patch(
        "pnpg.api.routes.threats.kill_process_windows", return_value=True
    ):
        response = await threats_client.post(
            "/api/v1/threats/1234/kill", headers=threats_auth_headers
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["remediation_status"] == "killed"


@pytest.mark.asyncio
async def test_kill_threat_process_not_found(
    threats_app, threats_client, threats_auth_headers
):
    conn = threats_app.state.db_pool._conn
    conn.fetchrow.return_value = None

    response = await threats_client.post(
        "/api/v1/threats/9999/kill", headers=threats_auth_headers
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_kill_threat_process_db_unavailable(
    threats_app, threats_client, threats_auth_headers
):
    threats_app.state.db_pool = None

    response = await threats_client.post(
        "/api/v1/threats/1234/kill", headers=threats_auth_headers
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_kill_threat_process_invalid_pid(
    threats_app, threats_client, threats_auth_headers
):
    response = await threats_client.post(
        "/api/v1/threats/0/kill", headers=threats_auth_headers
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_kill_threat_process_remediation_error(
    threats_app, threats_client, threats_auth_headers
):
    from pnpg.api.routes.threats import RemediationError

    conn = threats_app.state.db_pool._conn
    conn.fetchrow.return_value = {
        "threat_id": "11111111-1111-4111-8111-111111111111",
        "pid": 1234,
        "dst_ip": "93.184.216.34",
    }

    with mock.patch(
        "pnpg.api.routes.threats.kill_process_windows",
        side_effect=RemediationError("taskkill failed"),
    ):
        response = await threats_client.post(
            "/api/v1/threats/1234/kill", headers=threats_auth_headers
        )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/v1/threats/{pid}/block-ip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_block_threat_ip_success(
    threats_app, threats_client, threats_auth_headers
):
    conn = threats_app.state.db_pool._conn
    conn.fetchrow.return_value = {
        "threat_id": "11111111-1111-4111-8111-111111111111",
        "pid": 1234,
        "dst_ip": "93.184.216.34",
    }
    conn.execute.return_value = None

    with mock.patch(
        "pnpg.api.routes.threats.block_ip_windows_firewall", return_value=True
    ):
        response = await threats_client.post(
            "/api/v1/threats/1234/block-ip", headers=threats_auth_headers
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["ip"] == "93.184.216.34"
    assert payload["remediation_status"] == "blocked"


@pytest.mark.asyncio
async def test_block_threat_ip_not_found(
    threats_app, threats_client, threats_auth_headers
):
    conn = threats_app.state.db_pool._conn
    conn.fetchrow.return_value = None

    response = await threats_client.post(
        "/api/v1/threats/9999/block-ip", headers=threats_auth_headers
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_block_threat_ip_db_unavailable(
    threats_app, threats_client, threats_auth_headers
):
    threats_app.state.db_pool = None

    response = await threats_client.post(
        "/api/v1/threats/1234/block-ip", headers=threats_auth_headers
    )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_block_threat_ip_invalid_pid(
    threats_app, threats_client, threats_auth_headers
):
    response = await threats_client.post(
        "/api/v1/threats/0/block-ip", headers=threats_auth_headers
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_block_threat_ip_remediation_error(
    threats_app, threats_client, threats_auth_headers
):
    from pnpg.api.routes.threats import RemediationError

    conn = threats_app.state.db_pool._conn
    conn.fetchrow.return_value = {
        "threat_id": "11111111-1111-4111-8111-111111111111",
        "pid": 1234,
        "dst_ip": "93.184.216.34",
    }

    with mock.patch(
        "pnpg.api.routes.threats.block_ip_windows_firewall",
        side_effect=RemediationError("netsh firewall failed"),
    ):
        response = await threats_client.post(
            "/api/v1/threats/1234/block-ip", headers=threats_auth_headers
        )

    assert response.status_code == 500
