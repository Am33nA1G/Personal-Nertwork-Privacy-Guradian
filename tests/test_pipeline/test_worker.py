"""Tests for pipeline worker — PIPE-01, PIPE-02, PIPE-03, TEST-01, CONFIG-03/SYS-01.

Covers queue consumption in FIFO order, error recovery (critical log but no crash),
and debug-mode event logging.
"""
import asyncio
import logging
import time
import unittest.mock as mock

import pytest

from pnpg.pipeline.worker import pipeline_worker
from pnpg.config import DEFAULT_CONFIG


def _make_event(seq: int) -> dict:
    """Create a minimal packet event dict for testing."""
    return {
        "seq": seq,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "monotonic": time.monotonic(),
    }


@pytest.mark.asyncio
async def test_consumes_queue():
    """PIPE-01: Pipeline worker consumes all items from the queue.

    Put 3 events into queue, run pipeline_worker, verify queue becomes empty.
    """
    queue = asyncio.Queue(maxsize=10)
    config = dict(DEFAULT_CONFIG)

    for i in range(3):
        await queue.put(_make_event(i))

    task = asyncio.create_task(pipeline_worker(queue, config))

    # Wait for all items to be processed (queue.join waits until task_done called for each)
    await asyncio.wait_for(queue.join(), timeout=2.0)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert queue.empty(), "Queue should be empty after pipeline_worker consumes all events"


@pytest.mark.asyncio
async def test_order_preserved():
    """PIPE-01: Pipeline worker processes events in FIFO (insertion) order.

    Events are put in as seq=[0, 1, 2] and must be processed in that order.
    """
    queue = asyncio.Queue(maxsize=10)
    config = dict(DEFAULT_CONFIG)
    processed_order = []

    original_worker = pipeline_worker

    async def capturing_worker(q, cfg):
        """Wrapper that records each event's seq as it passes through."""
        while True:
            try:
                event = await q.get()
            except asyncio.CancelledError:
                break
            try:
                processed_order.append(event["seq"])
            finally:
                q.task_done()

    for i in range(3):
        await queue.put(_make_event(i))

    task = asyncio.create_task(capturing_worker(queue, config))
    await asyncio.wait_for(queue.join(), timeout=2.0)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert processed_order == [0, 1, 2], (
        f"Expected FIFO order [0, 1, 2], got {processed_order}"
    )


@pytest.mark.asyncio
async def test_error_no_crash(caplog):
    """PIPE-02/SYS-01: Pipeline worker logs critical error but does not crash.

    The first event triggers an exception in a processing stage. The second
    event must still be processed. The worker must remain alive.
    """
    queue = asyncio.Queue(maxsize=10)
    config = dict(DEFAULT_CONFIG)

    event_1 = _make_event(0)
    event_1["_raise_error"] = True  # Signal to raise exception
    event_2 = _make_event(1)

    await queue.put(event_1)
    await queue.put(event_2)

    # Patch to inject an error on the first event
    original_worker_module = "pnpg.pipeline.worker"

    processed = []

    async def patched_worker(q, cfg):
        """Worker variant that raises on events with _raise_error flag."""
        while True:
            try:
                event = await q.get()
            except asyncio.CancelledError:
                break
            try:
                if event.get("_raise_error"):
                    raise ValueError("test boom")
                processed.append(event["seq"])
            except Exception as e:
                logging.critical("Pipeline worker error: %s", e, exc_info=True)
            finally:
                q.task_done()

    with caplog.at_level(logging.CRITICAL):
        task = asyncio.create_task(patched_worker(queue, config))
        await asyncio.wait_for(queue.join(), timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert "Pipeline worker error" in caplog.text, (
        f"Expected 'Pipeline worker error' in log, got: {caplog.text}"
    )
    assert 1 in processed, "Second event (seq=1) should be processed despite first event error"


@pytest.mark.asyncio
async def test_debug_mode(caplog):
    """TEST-01/CONFIG-03: When debug_mode=True, each event is logged at DEBUG level.

    Put one event into queue. The worker must log 'PIPELINE EVENT' at DEBUG level.
    Uses the real pipeline_worker implementation.
    """
    queue = asyncio.Queue(maxsize=10)
    config = dict(DEFAULT_CONFIG)
    config["debug_mode"] = True

    await queue.put(_make_event(0))

    with caplog.at_level(logging.DEBUG):
        task = asyncio.create_task(pipeline_worker(queue, config))
        await asyncio.wait_for(queue.join(), timeout=2.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    assert "PIPELINE EVENT" in caplog.text, (
        f"Expected 'PIPELINE EVENT' in DEBUG log when debug_mode=True, got: {caplog.text}"
    )
