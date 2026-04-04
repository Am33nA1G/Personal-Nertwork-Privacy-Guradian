"""RED-phase tests for DNS resolver — TtlLruCache, resolve_hostname, enrich_dns."""
import asyncio
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pnpg.pipeline.dns_resolver import TtlLruCache, enrich_dns, resolve_hostname


def test_cache_get_miss():
    """TtlLruCache.get returns None for missing key."""
    cache = TtlLruCache(10, 60.0)
    assert cache.get("nonexistent") is None


def test_cache_set_get_roundtrip():
    """set then get returns stored value."""
    cache = TtlLruCache(10, 60.0)
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_cache_expired_entry():
    """Expired entries are not returned."""
    cache = TtlLruCache(10, 0.01)
    cache.set("key", "value")
    time.sleep(0.02)
    assert cache.get("key") is None


def test_cache_lru_eviction():
    """At maxsize, oldest key is evicted."""
    cache = TtlLruCache(3, 60.0)
    for k, v in [("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")]:
        cache.set(k, v)
    assert cache.get("a") is None
    assert cache.get("d") == "4"


def test_cache_move_to_end_on_get():
    """get() refreshes LRU order so recent reads are not evicted."""
    cache = TtlLruCache(3, 60.0)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.set("c", "3")
    cache.get("a")
    cache.set("d", "4")
    assert cache.get("a") is not None
    assert cache.get("b") is None


@pytest.mark.asyncio
async def test_resolves_known_ip():
    """DNS-01: PTR resolves to hostname."""
    cache = TtlLruCache(10, 60.0)
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_running_loop()
    with patch(
        "socket.gethostbyaddr",
        return_value=("example.com", [], ["1.2.3.4"]),
    ):
        result = await resolve_hostname("1.2.3.4", cache, executor, loop)
    assert result == "example.com"
    executor.shutdown(wait=False)


@pytest.mark.asyncio
async def test_dns_uses_executor():
    """DNS-02: gethostbyaddr runs via loop.run_in_executor."""
    cache = MagicMock()
    cache.get.return_value = None
    executor = ThreadPoolExecutor(max_workers=2)
    mock_loop = MagicMock()
    mock_loop.run_in_executor = AsyncMock(
        return_value=("resolved.example", [], ["1.2.3.4"])
    )
    with patch("socket.gethostbyaddr") as mock_ghba:
        await resolve_hostname("1.2.3.4", cache, executor, mock_loop)
        mock_loop.run_in_executor.assert_called_once()
        call_args = mock_loop.run_in_executor.call_args
        assert call_args[0][0] is executor
        assert call_args[0][1] is mock_ghba
        assert call_args[0][2] == "1.2.3.4"
    executor.shutdown(wait=False)


@pytest.mark.asyncio
async def test_timeout_fires():
    """DNS-03: timeout returns raw IP."""
    cache = TtlLruCache(10, 60.0)
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_running_loop()

    def slow_lookup(_ip):
        time.sleep(5)
        return ("slow", [], [])

    with patch(
        "socket.gethostbyaddr",
        side_effect=slow_lookup,
    ):
        result = await resolve_hostname(
            "192.0.2.1", cache, executor, loop, timeout=0.1
        )
    assert result == "192.0.2.1"
    executor.shutdown(wait=False)


@pytest.mark.asyncio
async def test_cache_hit():
    """DNS-04: second call does not invoke gethostbyaddr again."""
    cache = TtlLruCache(10, 60.0)
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_running_loop()
    with patch(
        "socket.gethostbyaddr",
        return_value=("cached.com", [], ["5.5.5.5"]),
    ) as mock_ghba:
        await resolve_hostname("5.5.5.5", cache, executor, loop)
        await resolve_hostname("5.5.5.5", cache, executor, loop)
    assert mock_ghba.call_count == 1
    executor.shutdown(wait=False)


@pytest.mark.asyncio
async def test_no_ptr_fallback():
    """DNS-05: socket.herror yields raw IP string."""
    cache = TtlLruCache(10, 60.0)
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_running_loop()
    with patch(
        "socket.gethostbyaddr",
        side_effect=socket.herror(1, "Unknown host"),
    ):
        result = await resolve_hostname("10.0.0.1", cache, executor, loop)
    assert result == "10.0.0.1"
    executor.shutdown(wait=False)


def test_cache_lru_eviction_at_1000():
    """DNS-06: 1001st insert evicts LRU entry."""
    cache = TtlLruCache(1000, 300)
    for i in range(1000):
        cache.set(f"k{i}", f"v{i}")
    cache.set("k1000", "last")
    assert cache.get("k0") is None
    assert cache.get("k1000") == "last"


@pytest.mark.asyncio
async def test_enrich_dns_immutable():
    """enrich_dns adds dst_hostname without mutating the original event."""
    event = {"dst_ip": "1.2.3.4", "seq": 42}
    cache = MagicMock()
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_running_loop()
    with patch(
        "pnpg.pipeline.dns_resolver.resolve_hostname",
        new_callable=AsyncMock,
        return_value="resolved.example",
    ):
        result = await enrich_dns(event, cache, executor, loop)
    assert "dst_hostname" not in event
    assert result["dst_hostname"] == "resolved.example"
    assert result["seq"] == 42
    executor.shutdown(wait=False)
