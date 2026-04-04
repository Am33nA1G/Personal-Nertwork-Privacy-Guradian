"""Process attribution module — psutil background poller and per-event enrichment.

Provides a TTL-expiring process cache keyed on (src_ip, src_port) and a
background asyncio task that refreshes it every poll_interval_ms milliseconds.

Requirements implemented:
  PROC-01: enrich_event() adds process_name and pid to every pipeline event.
  PROC-02: psutil.net_connections() is polled on a background schedule (200ms
           default) — NEVER called per-packet to avoid CPU spikes.
  PROC-03: Cache misses and expired entries return "unknown process" / pid=-1
           rather than crashing or raising exceptions.
  PROC-04: psutil.AccessDenied from net_connections() or Process.name() is
           caught and handled gracefully without clearing the cache.
  PROC-05: Cache is keyed on (laddr.ip, laddr.port) from psutil sconn, which
           matches the (src_ip, src_port) fields placed in events by queue_bridge.
  PROC-06: Cache entries carry an expires_at float (time.monotonic()) and are
           lazily expired on read — stale entries fall back to "unknown process".

IMPORTANT — cache reference invariant:
  The cache dict is passed by reference. _refresh_cache() mutates it in-place
  via cache.clear() + cache.update(). NEVER reassign the reference (cache = {})
  inside _refresh_cache — that would break the shared reference held by callers.
"""
import asyncio
import logging
import time

import psutil

logger = logging.getLogger(__name__)

# Only ESTABLISHED, SYN_SENT, and CLOSE_WAIT connections carry a concrete
# local address that matches an outgoing packet's src_ip. LISTEN sockets use
# 0.0.0.0 / :: laddr — those would never match and only pollute the cache.
VALID_STATUSES = frozenset({"ESTABLISHED", "SYN_SENT", "CLOSE_WAIT"})


def _refresh_cache(cache: dict, config: dict) -> None:
    """Rebuild the process attribution cache from the current OS connection table.

    Replaces cache contents in-place. All psutil calls are wrapped in
    try/except to handle AccessDenied from system processes (PROC-04).

    Cache key:   (laddr.ip, laddr.port) — a tuple of (str, int).
    Cache value: {"pid": int, "process_name": str, "expires_at": float}

    Args:
        cache:  The shared process cache dict (mutated in-place — PROC-05).
        config: Config dict providing proc_cache_ttl_sec (default 2).
    """
    ttl_secs = config.get("proc_cache_ttl_sec", 2)
    expires_at = time.monotonic() + ttl_secs

    try:
        conns = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        # Cannot read connection table — leave existing cache unchanged (PROC-04)
        logger.warning(
            "psutil.net_connections() raised AccessDenied — "
            "process cache not refreshed; previous entries retained"
        )
        return

    new_cache: dict = {}

    for conn in conns:
        if not conn.laddr:
            continue  # Skip connections with no local address
        if conn.status not in VALID_STATUSES:
            continue  # Skip LISTEN / TIME_WAIT / etc. (avoids 0.0.0.0 mismatch)

        key = (conn.laddr.ip, conn.laddr.port)

        if conn.pid is None:
            # PID not visible due to limited privileges — degrade gracefully
            new_cache[key] = {
                "pid": -1,
                "process_name": "unknown process",
                "expires_at": expires_at,
            }
            continue

        conn_pid = conn.pid
        try:
            name = psutil.Process(conn_pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process exited between net_connections() and Process() call, or
            # we lack permission to read its name — degrade gracefully (PROC-04)
            name = "unknown process"
            conn_pid = -1

        new_cache[key] = {
            "pid": conn_pid,
            "process_name": name,
            "expires_at": expires_at,
        }

    # Atomic in-place replacement — preserves the shared dict reference (PROC-05)
    cache.clear()
    cache.update(new_cache)


async def process_poller_loop(cache: dict, config: dict) -> None:
    """Background asyncio task that refreshes the process cache every poll_interval_ms.

    Runs as a pure asyncio task — psutil.net_connections() takes ~1.1ms on this
    machine (empirically verified), so it does not meaningfully block the event
    loop at a 200ms polling cadence.

    Handles asyncio.CancelledError for clean shutdown (mirrors the
    sniffer_supervisor and pipeline_worker patterns in this codebase).

    Args:
        cache:  The shared process cache dict (passed to _refresh_cache).
        config: Config dict providing poll_interval_ms (default 200ms).

    Requirements: PROC-02
    """
    interval = config.get("poll_interval_ms", 200) / 1000.0

    while True:
        try:
            _refresh_cache(cache, config)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break  # Clean shutdown — do not propagate
        except Exception:
            logger.critical(
                "process_poller_loop encountered an unexpected error",
                exc_info=True,
            )
            await asyncio.sleep(interval)  # Stay alive despite errors


def enrich_event(event: dict, cache: dict) -> dict:
    """Add process attribution fields to a pipeline event.

    Looks up (src_ip, src_port) in the process cache. If a valid, non-expired
    entry is found, returns a new event dict with process_name and pid populated.
    Falls back to "unknown process" / pid=-1 on cache miss or expired entry.

    CRITICAL: Returns a NEW dict via {**event, ...}. The original event is
    never mutated — project-wide immutability requirement from CLAUDE.md.

    Args:
        event: Flat event dict from make_packet_event() with src_ip, src_port.
        cache: The shared process attribution cache dict.

    Returns:
        New dict with all original fields plus 'process_name' (str) and 'pid' (int).

    Requirements: PROC-01, PROC-03, PROC-05, PROC-06
    """
    key = (event.get("src_ip"), event.get("src_port"))
    entry = cache.get(key)

    if entry is not None and time.monotonic() < entry["expires_at"]:
        # Valid cache hit — return new dict with process attribution (PROC-01)
        return {**event, "process_name": entry["process_name"], "pid": entry["pid"]}

    # Cache miss or expired entry — degrade gracefully (PROC-03 / PROC-06)
    return {**event, "process_name": "unknown process", "pid": -1}
