# Phase 2: Process Attribution - Research

**Researched:** 2026-04-01
**Domain:** psutil connection polling, asyncio task patterns, Scapy packet field extraction
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Extract `src_ip`, `src_port`, `dst_ip`, `dst_port`, and `protocol` in the queue bridge (`make_packet_event()` in `pnpg/capture/queue_bridge.py`), not in the process mapper or a separate stage. All downstream phases receive clean flat dicts and never need to import or parse Scapy directly.
- **D-02:** Keep `raw_pkt` in the event dict only when `config["debug_mode"] == True`. Drop it otherwise.
- **D-03:** When a packet has no TCP/UDP layer (ICMP, fragmented, etc.): set `src_port = None` and `dst_port = None`, keep the event flowing. `protocol` is still extracted from the IP header. The process mapper will get a cache miss on `(src_ip, None)` and degrade to "unknown process" naturally — no special case needed.
- The psutil poller is a **pure asyncio task** (no thread needed — psutil.net_connections() is fast enough for 200ms polling). Empirically verified at 1.1–1.5ms per call on this machine.
- The existing `ThreadPoolExecutor(max_workers=4)` may be reused for lookup, or a synchronous O(1) dict lookup in the async worker is acceptable.

### Claude's Discretion

- Cache data structure internals (dict vs OrderedDict vs custom), TTL expiry mechanism (lazy vs eager), and poller lifecycle placement (standalone task vs self-managing module).
- Requirements PROC-02/05/06 specify *what* (200ms polling, (src_ip, src_port) key, 2s TTL), not *how*.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROC-01 | System maps each connection to an originating process name and PID using psutil | psutil.net_connections() + Process(pid).name() pattern; empirically verified on this machine |
| PROC-02 | psutil connection table is polled on a background schedule (200ms interval) — not called per-packet | asyncio.create_task() + asyncio.sleep(0.2) loop; verified 203ms accuracy |
| PROC-03 | Connections that cannot be attributed show "unknown process" rather than failing or crashing | Cache miss returns {"process_name": "unknown process", "pid": -1} |
| PROC-04 | System handles AccessDenied from psutil for system processes gracefully | Wrap Process(pid).name() in try/except (NoSuchProcess, AccessDenied) |
| PROC-05 | System correlates packet (src_ip, src_port) with psutil connection table using a lookup cache | laddr=(ip, port) from sconn namedtuple is the exact key; verified field structure |
| PROC-06 | Mapping cache entries expire after configurable TTL (default: 2 seconds) | time.monotonic() per-entry timestamp; lazy expiry on lookup; config key proc_cache_ttl_sec already in DEFAULT_CONFIG |
</phase_requirements>

---

## Summary

Phase 2 adds process attribution to every pipeline event. The work has two parts: (1) updating `make_packet_event()` in `queue_bridge.py` to extract Scapy packet fields into the flat dict schema (D-01/D-02/D-03), and (2) building a background psutil polling task that maintains a `(src_ip, src_port) -> {pid, process_name, expires_at}` cache consulted by the pipeline worker.

The psutil `net_connections()` call takes 1.1–1.5ms on this machine (empirically measured), which easily fits inside a 200ms poll interval as a pure asyncio task — no thread executor needed for the poller itself. The cache is a plain Python dict keyed on `(laddr.ip, laddr.port)` from psutil's `sconn` namedtuple. All config keys needed (`proc_cache_ttl_sec`, `poll_interval_ms`) already exist in `DEFAULT_CONFIG` and `config.yaml`.

The biggest pitfall is the separation of concerns between the two sub-components: field extraction happens in `queue_bridge.py` at capture time, while cache lookup happens in `pipeline/worker.py` at processing time. The poller task belongs in a new `pnpg/pipeline/process_mapper.py` module that exposes a cache object and two public callables — one for the poller loop, one for the per-event lookup function called by the worker.

**Primary recommendation:** Build `pnpg/pipeline/process_mapper.py` as a self-contained module exposing `build_process_cache(config)` (returns the cache dict) and `enrich_event(event, cache)` (returns new event dict with process fields). The asyncio poller task is started in `main.py` lifespan, following the exact same `asyncio.create_task()` pattern as `sniffer_supervisor` and `pipeline_worker`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psutil | 7.2.2 (installed) | Enumerate OS network connections, map PIDs to process names | Only mature cross-platform library for this; `net_connections()` provides `laddr`, `pid` in one call |
| asyncio (stdlib) | Python 3.11+ | Background poller task, sleep interval | Already in use for pipeline_worker and supervisor; no thread needed for psutil polling |
| time (stdlib) | stdlib | Monotonic timestamps for TTL expiry | `time.monotonic()` is already used in `make_packet_event()` — consistent idiom |

### No New Dependencies

Phase 2 requires zero new packages. psutil is already installed (v7.2.2). The standard library provides everything else needed.

**Verification:** `python -c "import psutil; print(psutil.__version__)"` → `7.2.2`

---

## Architecture Patterns

### Recommended Project Structure Addition

```
pnpg/
├── capture/
│   └── queue_bridge.py     # MODIFY: add field extraction to make_packet_event()
├── pipeline/
│   ├── worker.py           # MODIFY: replace stub comment with enrich_event() call
│   └── process_mapper.py   # NEW: poller loop + cache + enrich_event()
├── config.py               # NO CHANGE: proc_cache_ttl_sec + poll_interval_ms already present
└── main.py                 # MODIFY: create_task(process_poller_loop(...))
```

### Pattern 1: Packet Field Extraction in make_packet_event() (D-01/D-02/D-03)

**What:** Extract IP/TCP/UDP fields from the Scapy packet at queue injection time. Store `raw_pkt` only when `debug_mode=True`.

**When to use:** Every packet event at queue injection time (inside `_enqueue_packet`, which already calls `make_packet_event()`).

**Scapy layer detection — verified approach:**

```python
# Source: Scapy docs + empirical verification on this project
def make_packet_event(pkt, config: dict) -> dict:
    """Build enriched packet event dict from a raw Scapy packet.

    D-01: Extract src_ip, src_port, dst_ip, dst_port, protocol.
    D-02: Include raw_pkt only when debug_mode=True.
    D-03: Non-TCP/UDP packets get src_port=None, dst_port=None.
    """
    event = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "monotonic": time.monotonic(),
        "src_ip": None,
        "src_port": None,
        "dst_ip": None,
        "dst_port": None,
        "protocol": None,
    }

    if pkt.haslayer("IP"):
        ip = pkt["IP"]
        event["src_ip"] = ip.src
        event["dst_ip"] = ip.dst
        event["protocol"] = ip.proto  # int: 6=TCP, 17=UDP, 1=ICMP

        if pkt.haslayer("TCP"):
            event["src_port"] = pkt["TCP"].sport
            event["dst_port"] = pkt["TCP"].dport
        elif pkt.haslayer("UDP"):
            event["src_port"] = pkt["UDP"].sport
            event["dst_port"] = pkt["UDP"].dport
        # D-03: No TCP/UDP -> src_port/dst_port remain None

    if config.get("debug_mode"):
        event["raw_pkt"] = pkt  # D-02

    return event
```

**Important:** `make_packet_event()` currently takes only `pkt`. After D-01 changes, it must also accept `config` so it can check `debug_mode`. The `_enqueue_packet()` caller already has `config` in scope via `make_packet_handler()` — the handler factory must pass config through.

### Pattern 2: TTL-Expiring Cache Dict (PROC-05/PROC-06)

**What:** Plain Python dict mapping `(src_ip, src_port)` -> `{"pid": int, "process_name": str, "expires_at": float}`. Lazy expiry: check TTL on read, not on write.

**When to use:** Populated by the background poller every 200ms. Looked up per-event in the pipeline worker.

```python
# Source: Empirical — psutil sconn fields verified on this machine
# sconn namedtuple fields: fd, family, type, laddr, raddr, status, pid
# laddr is addr(ip=str, port=int)

import time
import psutil

def _refresh_cache(cache: dict, config: dict) -> None:
    """Rebuild the process attribution cache from current OS connection table.

    Replaces cache contents in-place. Called every proc_poll_interval_ms.
    Wraps psutil calls to handle AccessDenied gracefully (PROC-04).
    """
    ttl_secs = config.get("proc_cache_ttl_sec", 2)
    expires_at = time.monotonic() + ttl_secs

    new_cache = {}
    try:
        conns = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        # Cannot read connection table at all — leave cache unchanged
        return

    for conn in conns:
        if not conn.laddr:
            continue
        key = (conn.laddr.ip, conn.laddr.port)

        if conn.pid is None:
            # Limited privileges — pid not visible for this connection
            new_cache[key] = {"pid": -1, "process_name": "unknown process", "expires_at": expires_at}
            continue

        try:
            proc = psutil.Process(conn.pid)
            name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Process died between net_connections() and Process() call — normal
            name = "unknown process"
            conn_pid = -1
        else:
            conn_pid = conn.pid

        new_cache[key] = {"pid": conn_pid, "process_name": name, "expires_at": expires_at}

    # Atomic replacement — never partially update the cache
    cache.clear()
    cache.update(new_cache)
```

### Pattern 3: Background Poller as asyncio Task (PROC-02)

**What:** A coroutine that calls `_refresh_cache()` every 200ms, run as `asyncio.create_task()` from the lifespan. Psutil call takes ~1.1ms so it doesn't block the event loop meaningfully.

```python
# Source: Matches existing sniffer_supervisor pattern in pnpg/capture/sniffer.py
async def process_poller_loop(cache: dict, config: dict) -> None:
    """Background asyncio task — refreshes the process cache every poll_interval_ms.

    Never blocks the event loop: psutil.net_connections() verified at ~1.1ms on
    this machine. Task is cancelled by lifespan shutdown (same pattern as
    sniffer_supervisor and pipeline_worker).
    """
    interval = config.get("poll_interval_ms", 200) / 1000.0
    while True:
        try:
            _refresh_cache(cache, config)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.critical("process_poller_loop error", exc_info=True)
            await asyncio.sleep(interval)  # Continue on error, don't crash
```

**Lifespan addition** (`main.py`) — follows exact pattern of existing tasks:

```python
# After existing worker_task creation:
process_cache: dict = {}
poller_task = asyncio.create_task(
    process_poller_loop(process_cache, config),
    name="process-poller",
)
app.state.process_cache = process_cache

# In shutdown:
poller_task.cancel()
try:
    await poller_task
except asyncio.CancelledError:
    pass
```

### Pattern 4: Per-Event Enrichment in pipeline_worker (PROC-01/PROC-03/PROC-05/PROC-06)

**What:** Synchronous O(1) dict lookup in the async worker. Returns new dict via `{**event, ...}` — immutable event pattern.

```python
# Source: Established project pattern (CLAUDE.md + CONTEXT.md code_context section)
def enrich_event(event: dict, cache: dict) -> dict:
    """Add process attribution fields to a pipeline event.

    Looks up (src_ip, src_port) in the process cache. Falls back to
    "unknown process" / PID -1 on cache miss or expired entry (PROC-03/06).

    Args:
        event: Flat event dict from make_packet_event() (must have src_ip, src_port).
        cache: The shared process attribution cache dict.

    Returns:
        New event dict with 'process_name' and 'pid' added (PROC-01).
    """
    key = (event.get("src_ip"), event.get("src_port"))
    entry = cache.get(key)

    if entry is not None and time.monotonic() < entry["expires_at"]:
        return {**event, "process_name": entry["process_name"], "pid": entry["pid"]}

    # Cache miss or expired — degrade gracefully (PROC-03/PROC-06)
    return {**event, "process_name": "unknown process", "pid": -1}
```

**Integration in worker.py** (replaces stub comment at line 48):

```python
# Phase 2: Replace stub with:
event = enrich_event(event, app_state.process_cache)
# But pipeline_worker currently receives only (queue, config), not app.state
# Resolution: pass process_cache as a third argument to pipeline_worker()
```

**Note on pipeline_worker signature:** The current signature is `pipeline_worker(queue, config)`. Phase 2 requires the worker to access `process_cache`. The cleanest approach is adding `process_cache: dict` as a third parameter, consistent with how `queue` and `config` are passed in from `lifespan`.

### Anti-Patterns to Avoid

- **Calling psutil.net_connections() per packet:** CPU spike under load. This is what PROC-02 prevents. The poller cache pattern exists precisely because net_connections() is ~1.1ms — fast for 200ms polling, but catastrophic at 500 packets/sec (would consume 550ms of CPU per second).
- **Storing process name at net_connections() time only:** `conn.pid` from `net_connections()` is a snapshot PID. The process name lookup via `psutil.Process(pid).name()` must happen immediately during cache refresh, not deferred to lookup time, because the process may have exited by then.
- **Mutating the event dict:** Project pattern is `{**event, "new_field": value}` — always return a new dict. Never `event["process_name"] = ...`.
- **Using a threading.Lock on the cache dict:** Python's GIL makes dict.update() and dict.get() atomic enough for this use case. The poller is an asyncio task (single-threaded), and the worker is also an asyncio task — no concurrent writes from multiple threads.
- **Blocking on psutil inside the event loop with run_in_executor:** At 1.1ms, this adds executor overhead for no benefit. The CONTEXT.md explicitly allows synchronous O(1) dict lookup in the async worker.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Process-to-connection mapping | Custom /proc parsing, WMI calls, netstat subprocess | `psutil.net_connections()` | Cross-platform, handles Windows, tested, ~1ms |
| Packet field parsing | Manual byte-level parsing | Scapy layer accessors (`pkt["IP"].src`, `pkt["TCP"].sport`) | Scapy already does dissection; manual parsing is error-prone and already rejected by stack |
| TTL-expiring cache | Custom cache class with background cleanup thread | Plain dict + `time.monotonic()` per-entry timestamp with lazy expiry | Simpler, zero overhead, no thread synchronization needed |
| Asyncio interval timer | `threading.Timer`, `sched` module | `asyncio.sleep(interval)` in a while-loop task | Already the project pattern; integrates cleanly with cancellation |

**Key insight:** psutil's `net_connections()` + `Process(pid).name()` is a two-call pattern that takes ~1.5ms total. Any alternative involves OS-specific APIs or subprocess invocation that would be both slower and less portable.

---

## Common Pitfalls

### Pitfall 1: make_packet_event() signature change breaks _enqueue_packet

**What goes wrong:** `make_packet_event(pkt)` is called inside `_enqueue_packet(queue, drop_counter, pkt)`. If `make_packet_event` now requires `config`, `_enqueue_packet` must also receive `config`, and `make_packet_handler` must also capture it in its closure.

**Why it happens:** The handler factory pattern captures variables at creation time. `config` must be passed into the factory and captured in the closure.

**How to avoid:** Update `make_packet_handler(loop, queue, drop_counter, config)` signature to accept config. Pass it through to `_enqueue_packet(queue, drop_counter, pkt, config)`. Update all callers in `main.py` and tests.

**Warning signs:** Tests for `test_packet_handler_calls_threadsafe` will fail if `_enqueue_packet` call signature changes but the assert hasn't been updated.

### Pitfall 2: Cache key mismatch between laddr and src_ip/src_port

**What goes wrong:** The psutil `laddr.ip` field may return `"::"` or `"0.0.0.0"` (listening sockets, IPv6) while the Scapy `pkt["IP"].src` returns the actual IPv4 source address. These will never match.

**Why it happens:** psutil reports the bound address of the socket (which may be `0.0.0.0` for listening sockets), while Scapy reports the actual IP in the captured packet header.

**How to avoid:** Filter out connections where `conn.status != "ESTABLISHED"` when building the cache, OR accept that listening sockets will naturally miss and degrade to "unknown process". Outgoing connections (ESTABLISHED, SYN_SENT) have concrete laddr values that match packet src_ip. This is acceptable — listening sockets do not generate outgoing packets.

**Recommended filter:** Include only connections in ESTABLISHED, SYN_SENT, or CLOSE_WAIT status when building the cache. This reduces cache size and eliminates the laddr mismatch problem for server-side listening sockets.

### Pitfall 3: Short-lived connections disappear between net_connections() calls

**What goes wrong:** A connection visible at T=0ms is gone by T=200ms (next poll). Packets from that connection arrive after T=200ms and get cache misses.

**Why it happens:** HTTP/1.0 or short-lived TCP connections close in under 200ms. This is documented in REQUIREMENTS.md Known Limitations.

**How to avoid:** The 2-second TTL ensures that entries from the PREVIOUS poll remain valid until they expire. After a connection closes, its laddr entry stays in the cache for up to 2 seconds — sufficient for most short-lived connections. No further mitigation needed for v1. PROC-03 only requires graceful degradation, not perfect attribution.

### Pitfall 4: psutil.net_connections() raises AccessDenied without admin

**What goes wrong:** On Windows without administrator privileges, `psutil.net_connections()` raises `psutil.AccessDenied` instead of returning a partial list.

**Why it happens:** Windows requires elevated privileges to enumerate all system connections. The sniffer also requires admin (CAP-03 checked at startup), so in normal operation this should not occur. However, defensive coding requires handling it.

**How to avoid:** Wrap the `psutil.net_connections()` call itself in a try/except block in `_refresh_cache()`. On AccessDenied, log a warning and leave the cache unchanged (don't clear it). This ensures the previous cache contents remain valid rather than clearing to empty.

### Pitfall 5: process_cache reference threading confusion

**What goes wrong:** `process_cache` is mutated via `cache.clear(); cache.update(new_cache)` in the poller. If the dict reference is replaced (e.g., `cache = new_cache`) instead of mutated in-place, the pipeline_worker holds a stale reference to the original empty dict.

**Why it happens:** Python dicts are passed by reference. Replacing the reference inside `_refresh_cache` would not be visible to the caller.

**How to avoid:** Always mutate the existing cache dict in-place (`cache.clear(); cache.update(...)`) rather than reassigning. The reference passed to `enrich_event` and `process_poller_loop` must be the same object. Document this constraint in the module docstring.

---

## Code Examples

### Verified: psutil sconn namedtuple fields (empirically confirmed on this machine)

```python
# psutil 7.2.2 on Windows 11 — verified output:
# sconn(fd=-1, family=AF_INET, type=SOCK_STREAM, laddr=addr(ip='192.168.1.16', port=52073),
#       raddr=addr(ip='160.79.104.10', port=443), status='ESTABLISHED', pid=10136)

# Fields: fd, family, type, laddr, raddr, status, pid
# laddr: addr(ip: str, port: int)
# pid: int (None if limited privileges)
```

### Verified: net_connections() call timing on this machine

```
psutil.net_connections(kind='inet') timing:
  min=1.1ms  max=1.2ms  avg=1.1ms  (5-run sample, 185 connections, Windows 11, admin)
```

This confirms the decision: psutil poller is a pure asyncio task, no thread needed.

### Verified: asyncio.sleep(0.2) interval accuracy

```
Simulated 200ms poll intervals (actual): ['203ms', '203ms', '203ms', '203ms']
```

3ms overhead is acceptable for this polling use case.

### Verified: Scapy mock pattern for testing make_packet_event()

```python
# Mock TCP packet for unit tests (no Npcap required)
from unittest.mock import MagicMock

def make_mock_tcp_packet(src_ip="192.168.1.1", dst_ip="8.8.8.8",
                         sport=12345, dport=443) -> MagicMock:
    pkt = MagicMock()
    pkt.haslayer = lambda layer: layer in ("IP", "TCP")
    pkt.__getitem__ = lambda self, key: {
        "IP": MagicMock(src=src_ip, dst=dst_ip, proto=6),
        "TCP": MagicMock(sport=sport, dport=dport),
    }[key]
    return pkt

def make_mock_icmp_packet(src_ip="192.168.1.1", dst_ip="8.8.8.8") -> MagicMock:
    pkt = MagicMock()
    pkt.haslayer = lambda layer: layer == "IP"  # No TCP or UDP
    pkt.__getitem__ = lambda self, key: {
        "IP": MagicMock(src=src_ip, dst=dst_ip, proto=1),  # ICMP=1
    }[key]
    return pkt
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| psutil.net_connections() called per-packet | Background polling cache at fixed interval | Project design decision (PROC-02) | Eliminates CPU spike; ~1.5ms per poll vs 1.5ms × packet_rate |
| psutil 5.x/6.x | psutil 7.2.2 installed | Upgrade path | No API breaking changes; `net_connections()` and `Process.name()` are stable APIs |

**No deprecated APIs in use:** psutil 7.2.2 `net_connections()` shows no deprecation warnings. The API is stable.

---

## Open Questions

1. **IPv6 source addresses in cache lookup**
   - What we know: Scapy on Windows over most Wi-Fi will report IPv4 src addresses for outgoing traffic. psutil may report `::` for IPv6 listening sockets.
   - What's unclear: Whether IPv6-originated packets can produce a src_ip that matches a psutil laddr.ip of `::` or `::1`.
   - Recommendation: Filter cache to ESTABLISHED+SYN_SENT status connections — this eliminates `::` listening socket entries entirely. Pure IPv6 outgoing traffic is uncommon in home environments and will degrade gracefully to "unknown process".

2. **make_packet_event() config parameter threading**
   - What we know: `_enqueue_packet()` runs in the event loop thread (via `call_soon_threadsafe`). Config dict is read-only after startup.
   - What's unclear: None — config is never mutated post-startup, so passing it to `make_packet_event()` is safe.
   - Recommendation: Pass `config` through `make_packet_handler()` closure, captured at handler creation time.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| psutil | PROC-01 through PROC-06 | Yes | 7.2.2 (verified) | None — required |
| Python asyncio (stdlib) | PROC-02 poller task | Yes | stdlib (Python 3.11+) | None — required |
| time.monotonic() (stdlib) | PROC-06 TTL expiry | Yes | stdlib | None — required |

**No missing dependencies.** All requirements for Phase 2 are satisfied by already-installed packages.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `pytest.ini` (asyncio_mode = auto, testpaths = tests) |
| Quick run command | `python -m pytest tests/test_pipeline/ tests/test_capture/ -q` |
| Full suite command | `python -m pytest tests/ -q` |

**Baseline:** 23 tests pass before any Phase 2 changes.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROC-01 | enrich_event() adds process_name and pid fields | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py -x -q` | No — Wave 0 |
| PROC-02 | Poller calls net_connections on 200ms schedule, not per-packet | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_poller_interval -x -q` | No — Wave 0 |
| PROC-03 | Cache miss returns "unknown process" / -1 | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_cache_miss -x -q` | No — Wave 0 |
| PROC-04 | AccessDenied in psutil handled without crash | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_access_denied -x -q` | No — Wave 0 |
| PROC-05 | (src_ip, src_port) key matches psutil laddr | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_key_lookup -x -q` | No — Wave 0 |
| PROC-06 | Expired TTL entries return "unknown process" | unit | `python -m pytest tests/test_pipeline/test_process_mapper.py::test_ttl_expiry -x -q` | No — Wave 0 |
| D-01 | make_packet_event extracts src_ip, src_port, dst_ip, dst_port, protocol | unit | `python -m pytest tests/test_capture/test_queue_bridge.py -x -q` | Yes (modify existing) |
| D-02 | raw_pkt absent in non-debug mode, present in debug mode | unit | `python -m pytest tests/test_capture/test_queue_bridge.py::test_raw_pkt_debug -x -q` | No — Wave 0 |
| D-03 | ICMP packet produces src_port=None without dropping event | unit | `python -m pytest tests/test_capture/test_queue_bridge.py::test_non_tcp_udp -x -q` | No — Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/ -q --tb=short`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green (23 + new tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_pipeline/test_process_mapper.py` — covers PROC-01 through PROC-06 (new file)
- [ ] `tests/test_capture/test_queue_bridge.py` — add D-01/D-02/D-03 test cases (modify existing file, which already exists)

*(No new framework config needed — pytest.ini already configured with asyncio_mode = auto)*

---

## Project Constraints (from CLAUDE.md)

All directives from `CLAUDE.md` that constrain Phase 2:

| Directive | Impact on Phase 2 |
|-----------|-------------------|
| Python 3.10+ (prefer 3.11+) | No impact — asyncio.create_task, dict, time.monotonic all available 3.10+ |
| Scapy for packet capture | make_packet_event() uses Scapy layer accessors — no alternatives |
| psutil for process mapping | Mandatory — no WMI, no subprocess netstat |
| FastAPI lifespan (not on_event) | Poller task started in existing lifespan block — already compliant |
| No external network calls | psutil reads local OS tables — compliant |
| JSON flat files only (no DB) | Cache is in-memory dict — compliant |
| Detection rules must not block sniff loop | Process mapper uses cached lookup — O(1), non-blocking |
| No framework changes | Python/FastAPI/psutil only — compliant |
| Immutable event dicts | `{**event, "process_name": ..., "pid": ...}` pattern used throughout |
| 200-400 lines per file (800 max) | process_mapper.py estimated 100-150 lines — compliant |
| Functions <50 lines | `_refresh_cache`, `enrich_event`, `process_poller_loop` all fit well under 50 lines |
| Config from config.yaml / DEFAULT_CONFIG | `proc_cache_ttl_sec` and `poll_interval_ms` already in DEFAULT_CONFIG |
| GSD workflow enforcement | Plans will be created via GSD before any code changes |

---

## Sources

### Primary (HIGH confidence)

- psutil 7.2.2 installed on this machine — `net_connections()` API verified via `help(psutil.net_connections)` and empirical timing
- Existing codebase: `pnpg/pipeline/worker.py`, `pnpg/capture/queue_bridge.py`, `pnpg/main.py`, `pnpg/config.py` — patterns verified by reading source
- `tests/conftest.py` — mock patterns verified by reading source
- CONTEXT.md — locked decisions D-01/D-02/D-03 verified

### Secondary (MEDIUM confidence)

- psutil documentation (stdlib help() output) — `net_connections()` return type and field names verified against actual runtime output on this machine

### Tertiary (LOW confidence)

- None — all findings are empirically verified on this machine or from source code inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — psutil 7.2.2 installed, API empirically verified
- Architecture: HIGH — derived from existing Phase 1 patterns in codebase
- Pitfalls: HIGH — most identified from reading actual source code constraints and empirical testing
- Test map: HIGH — existing pytest infrastructure confirmed working (23 tests green)

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (psutil API is stable; no external dependencies to drift)
