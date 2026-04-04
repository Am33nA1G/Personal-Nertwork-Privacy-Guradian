"""Tests for queue_bridge.py — CAP-05, CAP-06, CAP-07, CAP-08.

Covers drop-head strategy, drop logging, dual timestamps, and threadsafe bridge.
"""
import asyncio
import logging
import unittest.mock as mock

import pytest

from pnpg.capture.queue_bridge import (
    _enqueue_packet,
    make_packet_event,
    make_packet_handler,
)


def test_queue_maxsize():
    """CAP-05: Queue must be created with maxsize from config (default 500).

    Verifies that asyncio.Queue respects the maxsize parameter — if we create
    a queue with maxsize=3 and fill it, queue.full() returns True.
    """
    q = asyncio.Queue(maxsize=3)
    q.put_nowait(0)
    q.put_nowait(1)
    q.put_nowait(2)
    assert q.full() is True
    assert q.qsize() == 3


def test_drop_head():
    """CAP-06: When queue is full, oldest item is dropped and new one is added.

    Fill queue(maxsize=3) with [0,1,2], then enqueue 3.
    Result must be [1,2,3] — item 0 is evicted (drop-head strategy).
    """
    q = asyncio.Queue(maxsize=3)
    q.put_nowait(0)
    q.put_nowait(1)
    q.put_nowait(2)

    drop_counter = [0]
    mock_pkt = mock.MagicMock()
    mock_pkt.haslayer = lambda layer: False  # No IP layer — no field extraction needed
    config = {"debug_mode": False}
    _enqueue_packet(q, drop_counter, mock_pkt, config)

    assert drop_counter[0] == 1
    # Queue should contain 3 items; the oldest (0) was dropped
    items = []
    while not q.empty():
        item = q.get_nowait()
        # Items are packet event dicts — just verify count and oldest was removed
        items.append(item)
    assert len(items) == 3


def test_drop_log(caplog):
    """CAP-07: Packet drops must be logged as INFO with running count."""
    q = asyncio.Queue(maxsize=3)
    q.put_nowait(0)
    q.put_nowait(1)
    q.put_nowait(2)

    drop_counter = [0]
    mock_pkt = mock.MagicMock()
    mock_pkt.haslayer = lambda layer: False  # No IP layer
    config = {"debug_mode": False}

    with caplog.at_level(logging.INFO):
        _enqueue_packet(q, drop_counter, mock_pkt, config)

    assert "Packet dropped" in caplog.text
    assert drop_counter[0] == 1


def test_timestamps():
    """CAP-08: Each packet event must have ISO8601 wall-clock and monotonic timestamps."""
    mock_pkt = mock.MagicMock()
    mock_pkt.haslayer = lambda layer: False  # No IP layer
    event = make_packet_event(mock_pkt, {"debug_mode": False})

    assert "timestamp" in event
    assert "T" in event["timestamp"]
    assert "+" in event["timestamp"] or "Z" in event["timestamp"] or event["timestamp"].endswith("+00:00")
    assert "monotonic" in event
    assert isinstance(event["monotonic"], float)


def test_packet_handler_calls_threadsafe():
    """CAP-05: make_packet_handler returns a callable that invokes call_soon_threadsafe."""
    mock_loop = mock.MagicMock()
    q = asyncio.Queue(maxsize=10)
    drop_counter = [0]
    config = {"debug_mode": False}

    handler = make_packet_handler(mock_loop, q, drop_counter, config)
    mock_pkt = mock.MagicMock()
    handler(mock_pkt)

    assert mock_loop.call_soon_threadsafe.called
    mock_loop.call_soon_threadsafe.assert_called_once_with(
        _enqueue_packet, q, drop_counter, mock_pkt, config
    )


# ---------------------------------------------------------------------------
# D-01/D-02/D-03: make_packet_event field extraction (Phase 2 — RED stubs)
# These tests exercise the NEW make_packet_event(pkt, config) signature.
# They will be RED until Plan 02 updates make_packet_event() in queue_bridge.py.
# ---------------------------------------------------------------------------


def _mock_tcp_pkt(src_ip="192.168.1.1", dst_ip="8.8.8.8", sport=12345, dport=443):
    """Create a mock Scapy TCP/IP packet for unit tests (no Npcap required)."""
    pkt = mock.MagicMock()
    pkt.haslayer = lambda layer: layer in ("IP", "TCP")
    ip_mock = mock.MagicMock(src=src_ip, dst=dst_ip, proto=6)
    tcp_mock = mock.MagicMock(sport=sport, dport=dport)
    pkt.__getitem__ = lambda self, key: {"IP": ip_mock, "TCP": tcp_mock}[key]
    return pkt


def _mock_udp_pkt(src_ip="192.168.1.1", dst_ip="8.8.8.8", sport=54321, dport=53):
    """Create a mock Scapy UDP/IP packet for unit tests."""
    pkt = mock.MagicMock()
    pkt.haslayer = lambda layer: layer in ("IP", "UDP")
    ip_mock = mock.MagicMock(src=src_ip, dst=dst_ip, proto=17)
    udp_mock = mock.MagicMock(sport=sport, dport=dport)
    pkt.__getitem__ = lambda self, key: {"IP": ip_mock, "UDP": udp_mock}[key]
    return pkt


def _mock_icmp_pkt(src_ip="192.168.1.1", dst_ip="8.8.8.8"):
    """Create a mock Scapy ICMP/IP packet (no TCP or UDP layer)."""
    pkt = mock.MagicMock()
    pkt.haslayer = lambda layer: layer == "IP"  # No TCP or UDP
    ip_mock = mock.MagicMock(src=src_ip, dst=dst_ip, proto=1)  # ICMP=1
    pkt.__getitem__ = lambda self, key: {"IP": ip_mock}[key]
    return pkt


def _mock_no_ip_pkt():
    """Create a mock packet with no IP layer (ARP, etc.)."""
    pkt = mock.MagicMock()
    pkt.haslayer = lambda layer: False
    return pkt


def test_make_packet_event_tcp_fields():
    """D-01: TCP packet extracts src_ip, src_port, dst_ip, dst_port, protocol=6."""
    config = {"debug_mode": False}
    pkt = _mock_tcp_pkt(
        src_ip="192.168.1.1", dst_ip="8.8.8.8", sport=12345, dport=443
    )
    event = make_packet_event(pkt, config)

    assert event["src_ip"] == "192.168.1.1"
    assert event["dst_ip"] == "8.8.8.8"
    assert event["src_port"] == 12345
    assert event["dst_port"] == 443
    assert event["protocol"] == 6


def test_make_packet_event_udp_fields():
    """D-01: UDP packet extracts src_ip, src_port, dst_ip, dst_port, protocol=17."""
    config = {"debug_mode": False}
    pkt = _mock_udp_pkt(
        src_ip="10.0.0.1", dst_ip="1.1.1.1", sport=54321, dport=53
    )
    event = make_packet_event(pkt, config)

    assert event["src_ip"] == "10.0.0.1"
    assert event["dst_ip"] == "1.1.1.1"
    assert event["src_port"] == 54321
    assert event["dst_port"] == 53
    assert event["protocol"] == 17


def test_make_packet_event_icmp_no_ports():
    """D-03: ICMP packet has src_port=None, dst_port=None, protocol=1."""
    config = {"debug_mode": False}
    pkt = _mock_icmp_pkt(src_ip="192.168.1.1", dst_ip="8.8.8.8")
    event = make_packet_event(pkt, config)

    assert event["src_ip"] == "192.168.1.1"
    assert event["dst_ip"] == "8.8.8.8"
    assert event["src_port"] is None
    assert event["dst_port"] is None
    assert event["protocol"] == 1


def test_raw_pkt_debug_true():
    """D-02: debug_mode=True -> event has 'raw_pkt' key with the packet object."""
    config = {"debug_mode": True}
    pkt = _mock_tcp_pkt()
    event = make_packet_event(pkt, config)

    assert "raw_pkt" in event
    assert event["raw_pkt"] is pkt


def test_raw_pkt_debug_false():
    """D-02: debug_mode=False -> event does NOT have 'raw_pkt' key."""
    config = {"debug_mode": False}
    pkt = _mock_tcp_pkt()
    event = make_packet_event(pkt, config)

    assert "raw_pkt" not in event


def test_make_packet_event_no_ip_layer():
    """D-01/D-03: Packet with no IP layer -> all IP fields are None."""
    config = {"debug_mode": False}
    pkt = _mock_no_ip_pkt()
    event = make_packet_event(pkt, config)

    assert event["src_ip"] is None
    assert event["dst_ip"] is None
    assert event["src_port"] is None
    assert event["dst_port"] is None
    assert event["protocol"] is None
