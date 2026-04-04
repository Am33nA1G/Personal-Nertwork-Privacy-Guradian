"""DNS resolver — thread-pool reverse DNS with TTL+LRU cache.

DNS-01: Resolve destination IPs to domain names.
DNS-02: DNS lookups run in thread pool executor.
DNS-03: 2-second timeout per lookup.
DNS-04: Results cached with TTL (including negative caching).
DNS-05: Unresolvable IPs fall back to raw IP string.
DNS-06: Cache bounded to 1000 entries with LRU eviction.
"""

import asyncio
import logging
import socket
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

logger = logging.getLogger(__name__)


class TtlLruCache:
    """TTL-expiring LRU cache with a hard max size."""

    def __init__(self, maxsize: int, ttl: float) -> None:
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)
            self._cache[key] = (value, time.monotonic() + self.ttl)


async def resolve_hostname(
    ip: str,
    cache: TtlLruCache,
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop,
    timeout: float = 2.0,
) -> str:
    cached = cache.get(ip)
    if cached is not None:
        return cached

    hostname = ip
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(executor, socket.gethostbyaddr, ip),
            timeout=timeout,
        )
        hostname = result[0]
    except asyncio.TimeoutError:
        hostname = ip
    except (socket.herror, socket.gaierror):
        hostname = ip

    cache.set(ip, hostname)
    return hostname


async def enrich_dns(
    event: dict,
    cache: TtlLruCache,
    executor: ThreadPoolExecutor,
    loop: asyncio.AbstractEventLoop,
) -> dict:
    hostname = await resolve_hostname(
        event.get("dst_ip", ""), cache, executor, loop
    )
    return {**event, "dst_hostname": hostname}
