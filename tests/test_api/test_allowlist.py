"""Tests for allowlist CRUD routes."""

import pytest


@pytest.mark.asyncio
async def test_get_allowlist(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetch.return_value = [{"rule_id": "1", "dst_ip": "1.2.3.4"}]

    response = await api_client.get("/api/v1/allowlist", headers=api_auth_headers)

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_create_allowlist_rule(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchrow.return_value = {
        "rule_id": "11111111-1111-4111-8111-111111111111",
        "process_name": "chrome.exe",
        "dst_ip": "1.2.3.4",
        "dst_hostname": None,
        "expires_at": None,
        "reason": "ok",
    }

    response = await api_client.post(
        "/api/v1/allowlist",
        headers=api_auth_headers,
        json={"process_name": "chrome.exe", "dst_ip": "1.2.3.4", "reason": "ok"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["dst_ip"] == "1.2.3.4"
    assert api_app_with_state.state.detector_state.allowlist[0]["dst_ip"] == "1.2.3.4"


@pytest.mark.asyncio
async def test_delete_allowlist_rule(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    rule_id = "11111111-1111-4111-8111-111111111111"
    api_app_with_state.state.detector_state.allowlist = [{"rule_id": rule_id, "dst_ip": "1.2.3.4"}]
    conn.fetchrow.return_value = {"rule_id": rule_id}

    response = await api_client.delete(
        f"/api/v1/allowlist/{rule_id}",
        headers=api_auth_headers,
    )

    assert response.status_code == 200
    assert api_app_with_state.state.detector_state.allowlist == []


@pytest.mark.asyncio
async def test_delete_allowlist_not_found(api_app_with_state, api_client, api_auth_headers):
    conn = api_app_with_state.state.db_pool._conn
    conn.fetchrow.return_value = None
    rule_id = "11111111-1111-4111-8111-111111111111"

    response = await api_client.delete(
        f"/api/v1/allowlist/{rule_id}",
        headers=api_auth_headers,
    )

    assert response.status_code == 404
