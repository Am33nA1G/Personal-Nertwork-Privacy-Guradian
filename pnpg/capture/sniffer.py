"""Scapy sniffer daemon thread starter and supervisor coroutine.

CAP-01: Scapy sniff() runs in a daemon thread with store=False — packets are
        never accumulated in memory; each is processed via the prn= callback.
CAP-10: sniffer_supervisor wraps start_sniffer with exponential backoff restart.
        start_sniffer() itself is a simple single-run starter — it creates and
        starts the daemon thread and returns it.

SYS-01 / CONFIG-03: Exceptions inside the sniffer thread are caught and logged
at CRITICAL level so they don't silently disappear.
"""
import asyncio
import logging
import threading
from typing import Callable

from pnpg.capture.queue_bridge import make_packet_handler


logger = logging.getLogger(__name__)


def _sniffer_target(
    iface: str,
    packet_handler: Callable,
    stop_event: threading.Event,
) -> None:
    """Blocking target function that runs inside the daemon thread.

    Calls scapy.all.sniff() with store=False and a stop_filter that checks
    stop_event. Any exception is caught and logged at CRITICAL level.

    Args:
        iface:          Interface name (Scapy-compatible string or object).
        packet_handler: The callback returned by make_packet_handler(); called
                        by Scapy for each captured packet.
        stop_event:     Threading event; when set, stop_filter returns True and
                        sniff() exits on the next packet arrival.
    """
    try:
        from scapy.all import sniff  # pylint: disable=import-outside-toplevel

        sniff(
            iface=iface,
            prn=packet_handler,
            store=False,  # CAP-01 — no in-memory packet accumulation
            filter="ip",  # Capture IP traffic only
            stop_filter=lambda _: stop_event.is_set(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.critical("Sniffer thread died: %s", exc)  # SYS-01 / CONFIG-03


def start_sniffer(
    iface: str,
    packet_handler: Callable,
    stop_event: threading.Event,
) -> threading.Thread:
    """Start the Scapy sniffer in a daemon thread and return it.

    The returned thread is already started. The caller (supervisor coroutine
    in Plan 03) is responsible for joining/restarting on failure.

    CAP-01: Thread is daemon=True so it does not block process exit.

    Args:
        iface:          Interface name to sniff on.
        packet_handler: Packet callback (from make_packet_handler()).
        stop_event:     Set this to signal the sniffer to stop.

    Returns:
        The started daemon threading.Thread.
    """
    thread = threading.Thread(
        target=_sniffer_target,
        args=(iface, packet_handler, stop_event),
        daemon=True,  # CAP-01 — daemon thread does not block process exit
        name="pnpg-sniffer",
    )
    thread.start()
    return thread


async def sniffer_supervisor(
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue,
    iface: str,
    config: dict,
    drop_counter: list,
    stop_event: threading.Event,
) -> None:
    """Supervisor coroutine that restarts the sniffer thread on failure.

    CAP-10: Auto-restart with exponential backoff. Delay formula:
            min(1.0 * 2**attempt, 60.0) — starts at 1s, doubles each time,
            capped at 60s.

    The supervisor:
    1. Checks stop_event before each start — exits immediately if set.
    2. Starts the sniffer thread via start_sniffer().
    3. Awaits the thread's exit via run_in_executor (non-blocking join).
    4. If stop_event is set after thread exits, exits gracefully.
    5. Otherwise logs a warning with delay and attempt number, sleeps, restarts.

    Args:
        loop:         The running asyncio event loop.
        queue:        The bounded asyncio.Queue for packet events.
        iface:        Network interface name to sniff on.
        config:       Config dict (from load_config()).
        drop_counter: Mutable drop counter list [int].
        stop_event:   Threading event; set this to request graceful shutdown.
    """
    attempt = 0
    base_delay = 1.0
    max_delay = 60.0

    while True:
        if stop_event.is_set():
            break

        packet_handler = make_packet_handler(loop, queue, drop_counter, config)
        thread = start_sniffer(iface, packet_handler, stop_event)

        # Wait for the thread to exit WITHOUT blocking the event loop (RESEARCH Pitfall 5)
        await loop.run_in_executor(None, thread.join)

        if stop_event.is_set():
            break  # Graceful shutdown requested while thread was running

        # Thread died unexpectedly — restart with exponential backoff
        delay = min(base_delay * (2 ** attempt), max_delay)
        logger.warning(
            "Sniffer died, restarting in %.1fs (attempt %d)", delay, attempt + 1
        )
        await asyncio.sleep(delay)
        attempt += 1
