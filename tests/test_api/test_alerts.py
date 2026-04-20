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


@pytest.mark.asyncio
async def test_resolve_alert(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    alert_id = "11111111-1111-4111-8111-111111111111"
    api_app_with_state.state.detector_state.suppressed_alert_ids.add(alert_id)
    conn.fetchrow.return_value = {
        "alert_id": alert_id,
        "rule_id": "DET-05",
        "process_name": "chrome.exe",
        "status": "resolved",
        "suppressed": False,
    }

    response = await api_client.patch(
        f"/api/v1/alerts/{alert_id}",
        headers=api_auth_headers,
        json={"action": "resolve"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "resolved"
    assert alert_id not in api_app_with_state.state.detector_state.suppressed_alert_ids


@pytest.mark.asyncio
async def test_get_alerts_db_unavailable(api_app_with_state, api_client, api_auth_headers):
    api_app_with_state.state.db_pool = None

    response = await api_client.get("/api/v1/alerts", headers=api_auth_headers)

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_get_suppressions(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetch.return_value = [
        {"suppression_id": "1", "rule_id": "DET-05", "scope": "single"}
    ]

    response = await api_client.get("/api/v1/suppressions", headers=api_auth_headers)

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_get_suppressions_db_unavailable(
    api_app_with_state, api_client, api_auth_headers
):
    api_app_with_state.state.db_pool = None

    response = await api_client.get("/api/v1/suppressions", headers=api_auth_headers)

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_delete_suppression(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    suppression_id = "11111111-1111-4111-8111-111111111111"
    alert_id = "22222222-2222-4222-8222-222222222222"
    conn.fetchrow.return_value = {
        "suppression_id": suppression_id,
        "rule_id": "DET-05",
        "process_name": "chrome.exe",
        "scope": "single",
        "alert_id": alert_id,
    }

    response = await api_client.delete(
        f"/api/v1/suppressions/{suppression_id}",
        headers=api_auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True


@pytest.mark.asyncio
async def test_delete_suppression_rule_scope(
    api_app_with_state, api_client, api_auth_headers
):
    """Deleting a rule-scoped suppression also removes it from suppressed_rules."""
    conn = api_app_with_state.state.db_pool._conn
    suppression_id = "11111111-1111-4111-8111-111111111111"
    api_app_with_state.state.detector_state.suppressed_rules.add(("DET-05", "chrome.exe"))
    conn.fetchrow.return_value = {
        "suppression_id": suppression_id,
        "rule_id": "DET-05",
        "process_name": "chrome.exe",
        "scope": "rule",
        "alert_id": None,
    }

    response = await api_client.delete(
        f"/api/v1/suppressions/{suppression_id}",
        headers=api_auth_headers,
    )

    assert response.status_code == 200
    assert ("DET-05", "chrome.exe") not in (
        api_app_with_state.state.detector_state.suppressed_rules
    )


@pytest.mark.asyncio
async def test_delete_suppression_not_found(
    api_app_with_state, api_client, api_auth_headers
):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchrow.return_value = None
    suppression_id = "11111111-1111-4111-8111-111111111111"

    response = await api_client.delete(
        f"/api/v1/suppressions/{suppression_id}",
        headers=api_auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_suppression_db_unavailable(
    api_app_with_state, api_client, api_auth_headers
):
    api_app_with_state.state.db_pool = None
    suppression_id = "11111111-1111-4111-8111-111111111111"

    response = await api_client.delete(
        f"/api/v1/suppressions/{suppression_id}",
        headers=api_auth_headers,
    )

    assert response.status_code == 503
