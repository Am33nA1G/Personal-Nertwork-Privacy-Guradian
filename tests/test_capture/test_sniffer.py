"""Tests for sniffer supervisor — CAP-10.

Covers:
- Supervisor restarts dead sniffer threads (CAP-10)
- Exponential backoff delays between restarts
- Graceful stop when stop_event is set before starting
"""
import asyncio
import logging
import threading
import unittest.mock as mock

import pytest

from pnpg.capture.sniffer import sniffer_supervisor
from pnpg.config import DEFAULT_CONFIG


def _make_config():
    """Return a copy of DEFAULT_CONFIG for test use."""
    return dict(DEFAULT_CONFIG)


def _dead_thread_factory(stop_event=None):
    """Return a mock start_sniffer that creates threads which die immediately."""
    def fake_start_sniffer(iface, packet_handler, stop_event_arg):
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        t.join()  # Ensures thread is already dead when returned
        return t
    return fake_start_sniffer


@pytest.mark.asyncio
async def test_supervisor_restart(caplog):
    """CAP-10: Supervisor restarts the sniffer thread when it dies.

    Mock start_sniffer to return a thread that exits immediately.
    Run supervisor for enough iterations and assert restart occurred.
    """
    call_count = [0]
    stop_event = threading.Event()

    def fake_start_sniffer(iface, packet_handler, stop_evt):
        call_count[0] += 1
        if call_count[0] >= 3:
            # After 2 restarts, stop the supervisor
            stop_event.set()
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        return t

    queue = asyncio.Queue(maxsize=10)
    loop = asyncio.get_running_loop()
    config = _make_config()
    drop_counter = [0]

    with mock.patch("pnpg.capture.sniffer.start_sniffer", side_effect=fake_start_sniffer):
        with mock.patch("pnpg.capture.sniffer.make_packet_handler", return_value=lambda pkt: None):
            with caplog.at_level(logging.WARNING, logger="pnpg.capture.sniffer"):
                # Use asyncio.sleep patches to speed up the test
                with mock.patch("asyncio.sleep", return_value=None):
                    try:
                        await asyncio.wait_for(
                            sniffer_supervisor(loop, queue, "test_iface", config, drop_counter, stop_event),
                            timeout=2.0,
                        )
                    except asyncio.TimeoutError:
                        pass

    assert call_count[0] >= 2, f"Expected at least 2 start_sniffer calls, got {call_count[0]}"
    assert any(
        "restarting" in record.message.lower()
        for record in caplog.records
    ), "Expected 'restarting' in log messages"


@pytest.mark.asyncio
async def test_supervisor_backoff_delay():
    """CAP-10: Exponential backoff — first delay 1.0s, second delay 2.0s."""
    call_count = [0]
    stop_event = threading.Event()
    recorded_delays = []

    def fake_start_sniffer(iface, packet_handler, stop_evt):
        call_count[0] += 1
        if call_count[0] >= 3:
            stop_event.set()
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        return t

    async def fake_sleep(delay):
        recorded_delays.append(delay)

    queue = asyncio.Queue(maxsize=10)
    loop = asyncio.get_running_loop()
    config = _make_config()
    drop_counter = [0]

    with mock.patch("pnpg.capture.sniffer.start_sniffer", side_effect=fake_start_sniffer):
        with mock.patch("pnpg.capture.sniffer.make_packet_handler", return_value=lambda pkt: None):
            with mock.patch("asyncio.sleep", side_effect=fake_sleep):
                try:
                    await asyncio.wait_for(
                        sniffer_supervisor(loop, queue, "test_iface", config, drop_counter, stop_event),
                        timeout=2.0,
                    )
                except asyncio.TimeoutError:
                    pass

    assert len(recorded_delays) >= 2, f"Expected at least 2 sleep calls, got {recorded_delays}"
    assert recorded_delays[0] == 1.0, f"First delay should be 1.0s, got {recorded_delays[0]}"
    assert recorded_delays[1] == 2.0, f"Second delay should be 2.0s, got {recorded_delays[1]}"


@pytest.mark.asyncio
async def test_supervisor_graceful_stop():
    """CAP-10: When stop_event is set before starting, supervisor exits without restarting."""
    call_count = [0]
    stop_event = threading.Event()
    stop_event.set()  # Set before starting

    def fake_start_sniffer(iface, packet_handler, stop_evt):
        call_count[0] += 1
        t = threading.Thread(target=lambda: None, daemon=True)
        t.start()
        return t

    queue = asyncio.Queue(maxsize=10)
    loop = asyncio.get_running_loop()
    config = _make_config()
    drop_counter = [0]

    with mock.patch("pnpg.capture.sniffer.start_sniffer", side_effect=fake_start_sniffer):
        with mock.patch("pnpg.capture.sniffer.make_packet_handler", return_value=lambda pkt: None):
            with mock.patch("asyncio.sleep", return_value=None):
                try:
                    await asyncio.wait_for(
                        sniffer_supervisor(loop, queue, "test_iface", config, drop_counter, stop_event),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    pass

    # Supervisor checks stop_event at the top of the loop, so it should exit immediately
    # without calling start_sniffer at all (or at most once if it checks after starting)
    assert call_count[0] <= 1, f"Expected at most 1 start_sniffer call when stop_event is set, got {call_count[0]}"
