"""Tests for sniffer supervisor — CAP-10.

Tests exponential backoff restart, graceful stop via stop_event, and
proper delay sequencing on sniffer thread failure.
"""
import asyncio
import logging
import threading
import unittest.mock as mock

import pytest

from pnpg.capture.sniffer import sniffer_supervisor
from pnpg.config import DEFAULT_CONFIG


def _make_dead_thread():
    """Return a thread that exits immediately when started."""
    # Thread function that exits right away
    t = threading.Thread(target=lambda: None, daemon=True)
    t.start()
    t.join()  # Already dead
    return t


@pytest.mark.asyncio
async def test_supervisor_restart(caplog):
    """CAP-10: Supervisor restarts sniffer thread when it dies.

    Mock start_sniffer to return a thread that exits immediately. After
    allowing ~2 restart cycles, stop the supervisor and assert it called
    start_sniffer at least 2 times and logged a 'restarting' message.
    """
    config = dict(DEFAULT_CONFIG)
    queue = asyncio.Queue(maxsize=10)
    stop_event = threading.Event()
    call_count = [0]

    def fake_start_sniffer(iface, handler, stop_ev):
        call_count[0] += 1
        # Return a dead thread each time
        return _make_dead_thread()

    async def fake_sleep(delay):
        # Speed up test by sleeping a tiny amount instead of the real delay
        await asyncio.sleep(0.01)

    with mock.patch("pnpg.capture.sniffer.start_sniffer", side_effect=fake_start_sniffer):
        with mock.patch("asyncio.sleep", side_effect=fake_sleep):
            with caplog.at_level(logging.WARNING, logger="pnpg.capture.sniffer"):
                task = asyncio.create_task(
                    sniffer_supervisor(
                        asyncio.get_running_loop(),
                        queue,
                        "test_iface",
                        config,
                        [0],
                        stop_event,
                    )
                )
                # Wait for at least 2 restart cycles (short because sleep is mocked)
                await asyncio.sleep(0.1)
                stop_event.set()
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    assert call_count[0] >= 2, f"Expected at least 2 calls to start_sniffer, got {call_count[0]}"
    log_text = caplog.text.lower()
    assert "restarting" in log_text, f"Expected 'restarting' in log, got: {caplog.text}"


@pytest.mark.asyncio
async def test_supervisor_backoff_delay():
    """CAP-10: Exponential backoff — first delay 1.0s, second delay 2.0s.

    Formula: min(1.0 * 2**attempt, 60.0).
    """
    config = dict(DEFAULT_CONFIG)
    queue = asyncio.Queue(maxsize=10)
    stop_event = threading.Event()
    recorded_delays = []
    start_call_count = [0]

    def fake_start_sniffer(iface, handler, stop_ev):
        start_call_count[0] += 1
        # After 3 calls, set stop_event to end the supervisor
        if start_call_count[0] >= 3:
            stop_event.set()
        return _make_dead_thread()

    async def fake_sleep(delay):
        recorded_delays.append(delay)
        # Return immediately so test is fast
        return

    with mock.patch("pnpg.capture.sniffer.start_sniffer", side_effect=fake_start_sniffer):
        with mock.patch("asyncio.sleep", side_effect=fake_sleep):
            task = asyncio.create_task(
                sniffer_supervisor(
                    asyncio.get_running_loop(),
                    queue,
                    "test_iface",
                    config,
                    [0],
                    stop_event,
                )
            )
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    assert len(recorded_delays) >= 2, f"Expected at least 2 sleep calls, got {recorded_delays}"
    assert recorded_delays[0] == 1.0, f"First delay should be 1.0s, got {recorded_delays[0]}"
    assert recorded_delays[1] == 2.0, f"Second delay should be 2.0s, got {recorded_delays[1]}"


@pytest.mark.asyncio
async def test_supervisor_graceful_stop():
    """CAP-10: Supervisor exits without restarting when stop_event is set before start."""
    config = dict(DEFAULT_CONFIG)
    queue = asyncio.Queue(maxsize=10)
    stop_event = threading.Event()
    stop_event.set()  # Set BEFORE supervisor starts

    start_call_count = [0]

    def fake_start_sniffer(iface, handler, stop_ev):
        start_call_count[0] += 1
        return _make_dead_thread()

    with mock.patch("pnpg.capture.sniffer.start_sniffer", side_effect=fake_start_sniffer):
        with mock.patch("asyncio.sleep", return_value=None):
            task = asyncio.create_task(
                sniffer_supervisor(
                    asyncio.get_running_loop(),
                    queue,
                    "test_iface",
                    config,
                    [0],
                    stop_event,
                )
            )
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    # Supervisor should exit immediately — at most 1 start call (or 0 if stops before first start)
    assert start_call_count[0] <= 1, (
        f"Expected at most 1 start_sniffer call when stop_event is pre-set, "
        f"got {start_call_count[0]}"
    )
