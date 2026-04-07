"""Tests for stats summary and timeseries endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_stats_summary(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchrow.return_value = {
        "total_connections": 10,
        "unique_destinations": 5,
        "active_alerts": 2,
        "top_processes": [{"process_name": "chrome.exe", "count": 7}],
    }

    response = await api_client.get("/api/v1/stats/summary", headers=api_auth_headers)

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total_connections"] == 10
    assert "top_processes" in payload


@pytest.mark.asyncio
async def test_get_stats_timeseries(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetch.return_value = [
        {"bucket": "2026-04-05T12:00:00+00:00", "count": 3},
        {"bucket": "2026-04-05T13:00:00+00:00", "count": 4},
    ]

    response = await api_client.get("/api/v1/stats/timeseries", headers=api_auth_headers)

    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
