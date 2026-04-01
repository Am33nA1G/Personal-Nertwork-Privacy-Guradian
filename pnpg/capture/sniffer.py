"""Scapy sniffer daemon thread starter.

CAP-01: Scapy sniff() runs in a daemon thread with store=False — packets are
        never accumulated in memory; each is processed via the prn= callback.
CAP-10: (Supervisor) The supervisor coroutine (in Plan 03) wraps this function
        and handles auto-restart with exponential backoff. start_sniffer()
        itself is a simple single-run starter — it creates and starts the
        daemon thread and returns it.

SYS-01 / CONFIG-03: Exceptions inside the sniffer thread are caught and logged
at CRITICAL level so they don't silently disappear.
"""
import logging
import threading
from typing import Callable


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
