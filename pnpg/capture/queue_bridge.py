"""Thread-to-asyncio queue bridge with drop-head strategy.

CAP-05: Bounded asyncio.Queue feeds packets from the Scapy daemon thread to
        the event loop via call_soon_threadsafe.
CAP-06: When queue is full, oldest item is dropped (drop-head) — never blocks.
CAP-07: Packet drops are logged as INFO with a running total count.
CAP-08: Every packet event carries an ISO8601 wall-clock timestamp (UTC) and
        a monotonic timestamp for ordering and rate calculations.

Key constraint: asyncio.Queue is NOT thread-safe. All queue mutations
(_enqueue_packet) must run in the event loop thread. call_soon_threadsafe
enforces this — the Scapy daemon thread only schedules; it never touches the
queue directly.
"""
import asyncio
import datetime
import logging
import time
from typing import Callable


def make_packet_event(pkt) -> dict:
    """Build a packet event dict from a raw Scapy packet.

    CAP-08: Dual timestamps — ISO8601 wall-clock for human readability,
    monotonic for ordering and rate calculations.

    Args:
        pkt: Raw Scapy packet object.

    Returns:
        Dict with 'timestamp' (ISO8601 str), 'monotonic' (float), 'raw_pkt'.
    """
    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "monotonic": time.monotonic(),
        "raw_pkt": pkt,
    }


def _enqueue_packet(queue: asyncio.Queue, drop_counter: list, pkt) -> None:
    """Schedule a packet onto the asyncio queue from within the event loop thread.

    This function is called exclusively via loop.call_soon_threadsafe(), which
    guarantees it runs in the event loop thread — making get_nowait() and
    put_nowait() safe (asyncio.Queue internals are not thread-safe).

    CAP-06: If queue is full, drop the oldest item before inserting the new one
            (drop-head strategy — never blocks the Scapy thread).
    CAP-07: Log each drop as INFO with the running total count.

    Args:
        queue:        The bounded asyncio.Queue shared between sniffer and pipeline.
        drop_counter: A single-element list [int] used as a mutable integer counter.
                      (Lists are used because ints are immutable in Python closures.)
        pkt:          The raw Scapy packet to enqueue.
    """
    event = make_packet_event(pkt)

    if queue.full():
        try:
            queue.get_nowait()  # Evict oldest — drop-head strategy (CAP-06)
            drop_counter[0] += 1
            logging.info(  # CAP-07
                "Packet dropped (queue full). Total drops: %d", drop_counter[0]
            )
        except asyncio.QueueEmpty:
            pass  # Race guard — shouldn't happen but be safe

    queue.put_nowait(event)


def make_packet_handler(
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue,
    drop_counter: list,
) -> Callable:
    """Return the Scapy prn= callback that bridges the daemon thread to the event loop.

    CAP-05: The returned handler schedules _enqueue_packet onto the event loop
    via call_soon_threadsafe. The Scapy thread never touches the queue directly.

    Args:
        loop:         The running asyncio event loop (from asyncio.get_running_loop()).
        queue:        The bounded asyncio.Queue to enqueue packets onto.
        drop_counter: Mutable drop counter list shared with _enqueue_packet.

    Returns:
        A callable suitable for Scapy's sniff(prn=handler).
    """
    def handler(pkt) -> None:
        loop.call_soon_threadsafe(_enqueue_packet, queue, drop_counter, pkt)

    return handler
