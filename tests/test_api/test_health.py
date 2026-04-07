"""Tests for status and health endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_ok(api_app_with_state, api_client):
    response = await api_client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["status"] == "ok"
    assert payload["db"] == "ok"


@pytest.mark.asyncio
async def test_health_db_unavailable(api_app_with_state, api_client):
    api_app_with_state.state.db_pool = None

    response = await api_client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["data"]["db"] == "unavailable"


@pytest.mark.asyncio
async def test_status_requires_auth(api_client):
    response = await api_client.get("/api/v1/status")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_status_with_auth(api_client, api_auth_headers):
    response = await api_client.get("/api/v1/status", headers=api_auth_headers)

    assert response.status_code == 200
