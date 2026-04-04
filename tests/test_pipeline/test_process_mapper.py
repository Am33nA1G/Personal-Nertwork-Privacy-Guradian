"""Unit tests for process_mapper.py — PROC-01 through PROC-06.

Covers:
  PROC-01: enrich_event() adds process_name and pid fields to pipeline events.
  PROC-02: process_poller_loop calls _refresh_cache at ~200ms intervals.
  PROC-03: Cache miss or expired entry returns "unknown process" / pid=-1.
  PROC-04: psutil.AccessDenied during cache refresh does not crash or clear cache.
  PROC-05: Cache keyed on (src_ip, src_port) matching psutil laddr.ip/laddr.port.
  PROC-06: Cache entries expire after proc_cache_ttl_sec (lazy TTL check).
"""
import asyncio
import time
import unittest.mock as mock

import pytest

from pnpg.pipeline.process_mapper import (
    _refresh_cache,
    enrich_event,
    process_poller_loop,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sconn(
    ip="192.168.1.1",
    port=12345,
    pid=1234,
    status="ESTABLISHED",
):
    """Return a mock psutil sconn namedtuple-like object."""
    conn = mock.MagicMock()
    conn.laddr = mock.MagicMock()
    conn.laddr.ip = ip
    conn.laddr.port = port
    conn.pid = pid
    conn.status = status
    return conn


def _make_cache_with_entry(
    ip="192.168.1.1",
    port=12345,
    pid=1234,
    process_name="chrome.exe",
    ttl_offset=100,
):
    """Return a process cache dict with one valid (non-expired) entry."""
    return {
        (ip, port): {
            "pid": pid,
            "process_name": process_name,
            "expires_at": time.monotonic() + ttl_offset,
        }
    }


# ---------------------------------------------------------------------------
# PROC-01: enrich_event() adds process_name and pid fields
# ---------------------------------------------------------------------------


def test_enrich_event_cache_hit():
    """PROC-01: Cache hit returns event with process_name and pid from cache."""
    cache = _make_cache_with_entry(
        ip="192.168.1.1",
        port=12345,
        pid=1234,
        process_name="chrome.exe",
    )
    event = {
        "src_ip": "192.168.1.1",
        "src_port": 12345,
        "dst_ip": "8.8.8.8",
        "dst_port": 443,
    }
    result = enrich_event(event, cache)

    assert result["process_name"] == "chrome.exe"
    assert result["pid"] == 1234


def test_enrich_event_cache_miss():
    """PROC-01/PROC-03: Empty cache returns 'unknown process' and pid=-1."""
    cache = {}
    event = {
        "src_ip": "10.0.0.1",
        "src_port": 9999,
        "dst_ip": "1.1.1.1",
        "dst_port": 80,
    }
    result = enrich_event(event, cache)

    assert result["process_name"] == "unknown process"
    assert result["pid"] == -1


def test_enrich_event_returns_new_dict():
    """PROC-01: enrich_event must NOT mutate the original event dict."""
    cache = _make_cache_with_entry()
    event = {
        "src_ip": "192.168.1.1",
        "src_port": 12345,
        "dst_ip": "8.8.8.8",
        "dst_port": 443,
    }
    original_keys = set(event.keys())
    result = enrich_event(event, cache)

    # Must be a different object
    assert result is not event
    # Original must be unchanged
    assert set(event.keys()) == original_keys
    assert "process_name" not in event
    assert "pid" not in event
    # Result must include original fields
    assert result["src_ip"] == event["src_ip"]
    assert result["dst_ip"] == event["dst_ip"]


# ---------------------------------------------------------------------------
# PROC-02: process_poller_loop calls _refresh_cache at poll_interval_ms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poller_interval():
    """PROC-02: process_poller_loop calls asyncio.sleep with poll_interval_ms / 1000."""
    config = {"poll_interval_ms": 200, "proc_cache_ttl_sec": 2}
    cache = {}

    sleep_calls = []

    async def fake_sleep(interval):
        sleep_calls.append(interval)
        # Raise CancelledError after first sleep to exit loop
        if len(sleep_calls) >= 1:
            raise asyncio.CancelledError()

    with mock.patch(
        "pnpg.pipeline.process_mapper._refresh_cache"
    ) as mock_refresh, mock.patch(
        "asyncio.sleep", side_effect=fake_sleep
    ):
        try:
            await process_poller_loop(cache, config)
        except asyncio.CancelledError:
            pass

    # asyncio.sleep must have been called with 0.2 (200ms / 1000)
    assert len(sleep_calls) >= 1
    assert sleep_calls[0] == pytest.approx(0.2)
    assert mock_refresh.called


# ---------------------------------------------------------------------------
# PROC-03: Cache miss returns "unknown process" gracefully
# ---------------------------------------------------------------------------


def test_cache_miss_graceful():
    """PROC-03: Non-existent key in cache returns 'unknown process' and pid=-1."""
    cache = {
        ("192.168.1.1", 12345): {
            "pid": 1234,
            "process_name": "chrome.exe",
            "expires_at": time.monotonic() + 100,
        }
    }
    event = {"src_ip": "10.99.99.99", "src_port": 55555}
    result = enrich_event(event, cache)

    assert result["process_name"] == "unknown process"
    assert result["pid"] == -1


# ---------------------------------------------------------------------------
# PROC-04: psutil.AccessDenied handling in _refresh_cache
# ---------------------------------------------------------------------------


def test_access_denied_net_connections():
    """PROC-04: AccessDenied from psutil.net_connections() leaves cache unchanged."""
    import psutil

    config = {"proc_cache_ttl_sec": 2}
    # Pre-populate cache with one entry
    pre_existing_key = ("192.168.1.1", 12345)
    cache = {
        pre_existing_key: {
            "pid": 999,
            "process_name": "existing.exe",
            "expires_at": time.monotonic() + 100,
        }
    }

    with mock.patch(
        "psutil.net_connections", side_effect=psutil.AccessDenied(pid=0)
    ):
        _refresh_cache(cache, config)

    # Cache must still contain the pre-existing entry (not cleared)
    assert pre_existing_key in cache
    assert cache[pre_existing_key]["process_name"] == "existing.exe"


def test_access_denied_process_name():
    """PROC-04: AccessDenied from Process(pid).name() stores 'unknown process'."""
    import psutil

    config = {"proc_cache_ttl_sec": 2}
    cache = {}

    conn = _make_sconn(ip="192.168.1.1", port=12345, pid=1234, status="ESTABLISHED")

    mock_process = mock.MagicMock()
    mock_process.name.side_effect = psutil.AccessDenied(pid=1234)

    with mock.patch("psutil.net_connections", return_value=[conn]), mock.patch(
        "psutil.Process", return_value=mock_process
    ):
        _refresh_cache(cache, config)

    key = ("192.168.1.1", 12345)
    assert key in cache
    assert cache[key]["process_name"] == "unknown process"


# ---------------------------------------------------------------------------
# PROC-05: Cache key matches (src_ip, src_port) == (laddr.ip, laddr.port)
# ---------------------------------------------------------------------------


def test_key_lookup():
    """PROC-05: Cache keyed on (laddr.ip, laddr.port) matches event (src_ip, src_port)."""
    config = {"proc_cache_ttl_sec": 2}
    cache = {}

    conn = _make_sconn(ip="192.168.1.1", port=12345, pid=1234, status="ESTABLISHED")
    mock_process = mock.MagicMock()
    mock_process.name.return_value = "chrome.exe"

    with mock.patch("psutil.net_connections", return_value=[conn]), mock.patch(
        "psutil.Process", return_value=mock_process
    ):
        _refresh_cache(cache, config)

    # Event with matching (src_ip, src_port) should get the cached process
    event = {"src_ip": "192.168.1.1", "src_port": 12345, "dst_ip": "8.8.8.8"}
    result = enrich_event(event, cache)

    assert result["process_name"] == "chrome.exe"
    assert result["pid"] == 1234


# ---------------------------------------------------------------------------
# PROC-06: TTL expiry — expired entries return "unknown process"
# ---------------------------------------------------------------------------


def test_ttl_expiry():
    """PROC-06: Entry with expires_at in the past returns 'unknown process', pid=-1."""
    cache = {
        ("192.168.1.1", 12345): {
            "pid": 1234,
            "process_name": "chrome.exe",
            "expires_at": time.monotonic() - 10,  # 10 seconds in the past
        }
    }
    event = {"src_ip": "192.168.1.1", "src_port": 12345}
    result = enrich_event(event, cache)

    assert result["process_name"] == "unknown process"
    assert result["pid"] == -1


def test_ttl_valid():
    """PROC-06: Entry with expires_at in the future returns cached process_name and pid."""
    cache = {
        ("192.168.1.1", 12345): {
            "pid": 5678,
            "process_name": "firefox.exe",
            "expires_at": time.monotonic() + 100,  # 100 seconds in the future
        }
    }
    event = {"src_ip": "192.168.1.1", "src_port": 12345}
    result = enrich_event(event, cache)

    assert result["process_name"] == "firefox.exe"
    assert result["pid"] == 5678
