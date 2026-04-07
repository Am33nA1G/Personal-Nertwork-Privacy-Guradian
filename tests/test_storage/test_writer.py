"""Tests for Phase 5 storage writer."""

from datetime import datetime
import unittest.mock as mock
import uuid

import pytest

from pnpg.db.queries import INSERT_ALERT, INSERT_CONNECTION


def _make_event() -> dict:
    return {
        "event_id": "11111111-1111-4111-8111-111111111111",
        "timestamp": "2026-04-05T12:00:00+00:00",
        "process_name": "chrome.exe",
        "process_path": "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "pid": 1234,
        "src_ip": "192.168.1.5",
        "src_port": 52341,
        "dst_ip": "93.184.216.34",
        "dst_port": 443,
        "dst_hostname": "example.com",
        "dst_country": "US",
        "dst_asn": "AS15133",
        "dst_org": "EdgeCast Networks",
        "protocol": "TCP",
        "bytes_sent": 512,
        "bytes_recv": 2048,
        "state": "ESTABLISHED",
        "severity": "INFO",
        "threat_intel": {"is_blocklisted": False, "source": None},
    }


def _make_alert() -> dict:
    return {
        "alert_id": "22222222-2222-4222-8222-222222222222",
        "timestamp": "2026-04-05T12:00:01+00:00",
        "severity": "CRITICAL",
        "rule_id": "DET-05",
        "reason": "Connection to blocklisted destination",
        "confidence": 0.95,
        "process_name": "chrome.exe",
        "pid": 1234,
        "dst_ip": "93.184.216.34",
        "dst_hostname": "example.com",
        "recommended_action": "BLOCK",
        "suppressed": False,
        "status": "active",
    }


def _make_pool_and_conn():
    conn = mock.AsyncMock()
    acquire_cm = mock.AsyncMock()
    acquire_cm.__aenter__.return_value = conn
    acquire_cm.__aexit__.return_value = False

    pool = mock.MagicMock()
    pool.acquire.return_value = acquire_cm
    return pool, conn


@pytest.mark.asyncio
async def test_storage_writer_inserts_connection():
    from pnpg.storage.writer import storage_writer

    event = _make_event()
    pool, conn = _make_pool_and_conn()
    ndjson_writer = mock.AsyncMock()

    await storage_writer(event, [], pool, ndjson_writer)

    call = conn.execute.await_args_list[0]
    assert call.args[0] == INSERT_CONNECTION
    assert len(call.args) == 22
    assert isinstance(call.args[1], uuid.UUID)
    assert isinstance(call.args[2], datetime)
    assert isinstance(call.args[14], str)


@pytest.mark.asyncio
async def test_storage_writer_appends_ndjson_connection():
    from pnpg.storage.writer import storage_writer

    event = _make_event()
    pool, _conn = _make_pool_and_conn()
    ndjson_writer = mock.AsyncMock()

    await storage_writer(event, [], pool, ndjson_writer)

    ndjson_writer.append.assert_any_await("connections", event)


@pytest.mark.asyncio
async def test_storage_writer_inserts_alerts():
    from pnpg.storage.writer import storage_writer

    event = _make_event()
    alert = _make_alert()
    pool, conn = _make_pool_and_conn()
    ndjson_writer = mock.AsyncMock()

    await storage_writer(event, [alert], pool, ndjson_writer)

    alert_call = next(
        call for call in conn.execute.await_args_list if call.args[0] == INSERT_ALERT
    )
    assert isinstance(alert_call.args[1], uuid.UUID)
    assert isinstance(alert_call.args[2], datetime)
    ndjson_writer.append.assert_any_await("alerts", alert)


@pytest.mark.asyncio
async def test_storage_writer_pool_none_no_crash():
    from pnpg.storage.writer import storage_writer

    event = _make_event()
    ndjson_writer = mock.AsyncMock()

    await storage_writer(event, [], None, ndjson_writer)

    ndjson_writer.append.assert_awaited_once_with("connections", event)


@pytest.mark.asyncio
async def test_storage_writer_db_error_continues_ndjson():
    from pnpg.storage.writer import storage_writer

    event = _make_event()
    pool, conn = _make_pool_and_conn()
    ndjson_writer = mock.AsyncMock()
    conn.execute.side_effect = Exception("db boom")

    await storage_writer(event, [], pool, ndjson_writer)

    ndjson_writer.append.assert_awaited_once_with("connections", event)
