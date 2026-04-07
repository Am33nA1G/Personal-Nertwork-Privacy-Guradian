"""Tests for /api/v1/alerts and suppression endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_alerts_returns_paginated(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchval.return_value = 1
    conn.fetch.return_value = [{"alert_id": "1", "rule_id": "DET-05", "status": "active"}]

    response = await api_client.get("/api/v1/alerts", headers=api_auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 1
    assert payload["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_suppress_alert(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    alert_id = "11111111-1111-4111-8111-111111111111"
    conn.fetchrow.side_effect = [
        {
            "alert_id": alert_id,
            "rule_id": "DET-05",
            "process_name": "chrome.exe",
            "status": "suppressed",
            "suppressed": True,
        },
        {"suppression_id": "1"},
    ]

    response = await api_client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers=api_auth_headers,
        json={"action": "suppress", "reason": "test"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "suppressed"
    assert alert_id in api_app_with_state.state.detector_state.suppressed_alert_ids


@pytest.mark.asyncio
async def test_suppress_alert_not_found(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchrow.return_value = None
    alert_id = "11111111-1111-4111-8111-111111111111"

    response = await api_client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers=api_auth_headers,
        json={"action": "suppress"},
    )

    assert response.status_code == 404
