"""Tests for /api/v1/connections."""

import pytest


@pytest.mark.asyncio
async def test_get_connections_returns_paginated(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchval.return_value = 2
    conn.fetch.return_value = [
        {"event_id": "1", "process_name": "chrome.exe"},
        {"event_id": "2", "process_name": "firefox.exe"},
    ]

    response = await api_client.get("/api/v1/connections", headers=api_auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 2
    assert payload["pagination"] == {"page": 1, "page_size": 50, "total": 2}


@pytest.mark.asyncio
async def test_get_connections_filter_by_process(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []

    response = await api_client.get(
        "/api/v1/connections?process=chrome",
        headers=api_auth_headers,
    )

    assert response.status_code == 200
    assert conn.fetch.await_args.args[1] == "chrome"


@pytest.mark.asyncio
async def test_get_connections_db_unavailable(api_app_with_state, api_client, api_auth_headers):
    api_app_with_state.state.db_pool = None

    response = await api_client.get("/api/v1/connections", headers=api_auth_headers)

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_get_connections_rate_limited(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchval.return_value = 0
    conn.fetch.return_value = []

    responses = []
    for _ in range(101):
        responses.append(
            await api_client.get("/api/v1/connections", headers=api_auth_headers)
        )

    assert responses[0].status_code == 200
    assert responses[-1].status_code == 429
