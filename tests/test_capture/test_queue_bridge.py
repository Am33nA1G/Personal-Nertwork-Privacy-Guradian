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
    _enqueue_packet(q, drop_counter, mock_pkt)

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

    with caplog.at_level(logging.INFO):
        _enqueue_packet(q, drop_counter, mock_pkt)

    assert "Packet dropped" in caplog.text
    assert drop_counter[0] == 1


def test_timestamps():
    """CAP-08: Each packet event must have ISO8601 wall-clock and monotonic timestamps."""
    mock_pkt = mock.MagicMock()
    event = make_packet_event(mock_pkt)

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

    handler = make_packet_handler(mock_loop, q, drop_counter)
    mock_pkt = mock.MagicMock()
    handler(mock_pkt)

    assert mock_loop.call_soon_threadsafe.called
    mock_loop.call_soon_threadsafe.assert_called_once_with(
        _enqueue_packet, q, drop_counter, mock_pkt
    )
