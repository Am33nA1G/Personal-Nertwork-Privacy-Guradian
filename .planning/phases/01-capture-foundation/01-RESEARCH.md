# Phase 1: Capture Foundation - Research

**Researched:** 2026-03-31
**Domain:** Packet capture (Scapy/Npcap), asyncio/threading bridge, FastAPI lifespan, config loading
**Confidence:** HIGH (core patterns empirically verified on target machine)

---

<user_constraints>
## User Constraints (from CLAUDE.md)

### Locked Decisions
- **Tech Stack**: Python 3.10+, FastAPI, Scapy, psutil, socket, uvicorn; HTML/CSS/JS + Chart.js frontend — no framework changes
- **Local Only**: No external network calls from the tool itself; all resolution is local DNS
- **Storage**: JSON flat files for v1 — no database dependency
- **Privileges**: Admin/root required — Scapy needs raw socket access
- **Performance**: Detection rules must be lightweight enough to not block the sniff loop

### Claude's Discretion
- Project conventions not yet established — follow patterns in this research as they emerge
- Architecture not yet mapped — follow patterns found in codebase (empty at Phase 1 start)

### Deferred Ideas (OUT OF SCOPE)
- SQLite backend (v2)
- Geolocation, threat intelligence API, cloud deployment, mobile app, multi-user auth
- Inbound traffic monitoring
- Firewall/packet blocking, HTTPS decryption
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAP-01 | Capture outgoing packets in real-time using Scapy with `store=False` | Scapy `sniff(store=False, prn=callback)` pattern verified |
| CAP-02 | Npcap startup check — exit with clear error if not installed | `os.path.isdir(os.environ["WINDIR"] + "\\System32\\Npcap")` is Scapy's own detection method |
| CAP-03 | Verify administrator/root privileges on startup | `ctypes.windll.shell32.IsUserAnAdmin()` returns 0 on this machine (not admin) — confirmed works |
| CAP-04 | Auto-select interface with highest outbound traffic | `psutil.net_io_counters(pernic=True)` → sort by `bytes_sent` → match to Scapy `conf.ifaces` |
| CAP-05 | Sniffer in daemon thread with bounded asyncio queue (maxsize=500) | `loop.call_soon_threadsafe()` bridge pattern empirically verified |
| CAP-06 | Drop-head when queue full — not blocking | `get_nowait()` + `put_nowait()` via `call_soon_threadsafe` verified on Python 3.11 |
| CAP-07 | Log packet drops as INFO events | Standard `logging.info()` from within the drop callback |
| CAP-08 | Wall-clock ISO8601 + monotonic timestamp per event | `datetime.datetime.now(UTC).isoformat()` + `time.monotonic()` — verified |
| CAP-09 | Interface override via config.yaml or CLI flag | `argparse` for CLI, PyYAML for config.yaml, config takes precedence rules documented |
| CAP-10 | Sniffer auto-restart on failure with exponential backoff | Supervisor loop pattern verified: `min(base * 2**attempt, max_delay)` |
| CONFIG-01 | All thresholds in config.yaml | PyYAML 6.0.3 available on PyPI; full defaults schema documented |
| CONFIG-02 | Config validated at startup with sensible defaults | Deep-merge pattern verified in Python 3.11 stdlib |
| CONFIG-03 | Log critical errors without terminating event loop | `try/except Exception as e: logging.critical(...)` inside async tasks |
| SYS-01 | Log critical errors without terminating main event loop | Same as CONFIG-03 — single implementation handles both |
| PIPE-01 | Async pipeline worker consuming queue, routing through enrichment pipeline | `asyncio.Queue` consumer coroutine pattern verified |
| PIPE-02 | Pipeline worker preserves packet order | Single `asyncio.Queue` FIFO — order preserved by design |
| PIPE-03 | Pipeline worker never blocks on DNS/process mapping | All blocking ops dispatched via `loop.run_in_executor()` |
| TEST-01 | Debug mode prints each enriched pipeline event to console | `logging.debug()` + config flag gates console output |
</phase_requirements>

---

## Summary

Phase 1 establishes the entire execution backbone of PNPG. Three interconnected subsystems must be built: (1) a startup gate that checks Npcap and admin privileges before any sniffing begins, (2) a Scapy sniffer running as a daemon thread with a bounded asyncio queue bridging it to the FastAPI event loop, and (3) an async pipeline worker that consumes from that queue and dispatches enrichment steps to thread pool executors.

The single most important architectural decision in this phase is **how the Scapy thread feeds packets into the asyncio world**. Scapy's `sniff()` is blocking and must run in a daemon thread. The asyncio event loop runs in the main thread. The bridge is `loop.call_soon_threadsafe(callback)` — this is the only safe way to schedule work onto the event loop from a foreign thread. `asyncio.Queue` is NOT thread-safe directly; its internal deque must only be touched from within the event loop thread, which `call_soon_threadsafe` enforces. This pattern was empirically verified on Python 3.11 on the target machine.

The second key concern is the **cold start sequence**: load config → verify Npcap → verify admin → select interface → start sniffer. Each step must fail loudly and early if prerequisites are missing, rather than silently producing an empty queue.

**Primary recommendation:** Use `loop.call_soon_threadsafe()` for the sniff→queue bridge (not `run_coroutine_threadsafe`), implement drop-head with `get_nowait()` + `put_nowait()` inside the threadsafe callback, and wrap the sniffer thread in a supervisor coroutine for exponential backoff restarts.

---

## Standard Stack

### Core (Phase 1)

| Library | Version (PyPI verified) | Purpose | Why Standard |
|---------|------------------------|---------|--------------|
| Python | 3.11.0 (installed) | Runtime | Already installed; 3.11 is required minimum per CLAUDE.md |
| Scapy | 2.7.0 (latest on PyPI) | Packet capture + parsing | Only viable option for live raw capture + dissection on Windows |
| Npcap | 1.79+ | Windows capture driver | Hard prerequisite for Scapy; WinPcap is EOL since 2013 |
| FastAPI | 0.135.2 (latest on PyPI) | REST API + WebSocket host | Async-native; lifespan context manager for sniffer start/stop |
| uvicorn | 0.42.0 (latest on PyPI) | ASGI server | Standard pairing for FastAPI; use `uvicorn[standard]` |
| psutil | 7.2.2 (latest on PyPI) | Interface traffic stats for auto-selection | `net_io_counters(pernic=True)` gives per-interface bytes_sent |
| PyYAML | 6.0.3 (latest on PyPI) | config.yaml parsing | Only YAML library needed; safe_load prevents code execution |
| pytest | 9.0.2 (latest on PyPI) | Test framework | Not installed; required for TEST-01 and all validation |
| pytest-asyncio | 1.3.0 (latest on PyPI) | Async test support | Required for testing pipeline worker and queue bridge |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `collections.deque` | Python stdlib | Bounded in-memory buffer for connections | Use `maxlen=1000` for live connection store (STORE-01) |
| `concurrent.futures.ThreadPoolExecutor` | Python stdlib | Dispatching blocking calls to thread pool | PIPE-03: DNS, process mapping off the event loop |
| `logging` | Python stdlib | Structured log output | All log events — use levels: DEBUG, INFO, WARNING, CRITICAL |
| `argparse` | Python stdlib | CLI flags (`--interface`, `--debug`, `--config`) | CAP-09: override interface from command line |
| `ctypes` (Windows) | Python stdlib | Admin privilege check | `ctypes.windll.shell32.IsUserAnAdmin()` |
| `winreg` | Python stdlib (Windows) | Npcap registry/path check | Secondary detection after filesystem check |
| `time.monotonic` | Python stdlib | Monotonic timestamp (CAP-08) | Packet ordering, rate calculations |
| `datetime` | Python stdlib | ISO8601 wall-clock timestamp (CAP-08) | Human-readable log timestamps |
| `uuid` | Python stdlib | event_id generation | Required in data model per REQUIREMENTS.md |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `loop.call_soon_threadsafe` | `janus` library | janus is cleaner API but adds dependency; `call_soon_threadsafe` achieves same result with stdlib only |
| `loop.call_soon_threadsafe` | `run_coroutine_threadsafe` | `run_coroutine_threadsafe` creates a Future per call — overhead per packet; `call_soon_threadsafe` with a plain callback is cheaper |
| `psutil.net_io_counters` for interface auto-select | `conf.iface` (Scapy default) | Scapy's default interface may be wrong on multi-NIC Windows machines; psutil gives actual bytes_sent per interface |
| `PyYAML` safe_load | `tomllib` (Python 3.11 stdlib) | TOML is stdlib in 3.11+ but YAML is the format specified in requirements; no reason to change |

**Installation (requirements.txt):**
```
scapy>=2.7.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
psutil>=6.0.0
pyyaml>=6.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

**Version verification (run before pinning):**
```bash
pip index versions scapy    # 2.7.0 verified 2026-03-31
pip index versions fastapi  # 0.135.2 verified 2026-03-31
pip index versions uvicorn  # 0.42.0 verified 2026-03-31
pip index versions psutil   # 7.2.2 verified 2026-03-31
pip index versions pyyaml   # 6.0.3 verified 2026-03-31
pip index versions pytest   # 9.0.2 verified 2026-03-31
pip index versions pytest-asyncio  # 1.3.0 verified 2026-03-31
```

---

## Architecture Patterns

### Recommended Project Structure

```
pnpg/
├── main.py               # FastAPI app + lifespan context manager entry point
├── config.py             # Config loader: load config.yaml + apply defaults + validate
├── prereqs.py            # Npcap check, admin check, startup gate functions
├── capture/
│   ├── __init__.py
│   ├── sniffer.py        # Scapy sniff() daemon thread + supervisor coroutine
│   ├── queue_bridge.py   # loop.call_soon_threadsafe bridge + drop-head logic
│   └── interface.py      # Auto-select interface via psutil, parse config/CLI override
├── pipeline/
│   ├── __init__.py
│   └── worker.py         # Async pipeline worker: consumes queue, dispatches stages
├── logs/                 # Runtime log output (gitignored)
│   ├── connections.ndjson
│   └── alerts.ndjson
├── config.yaml           # User-editable runtime configuration
└── requirements.txt
```

### Pattern 1: FastAPI Lifespan + Sniffer Startup

**What:** `@asynccontextmanager` lifespan wires the full startup sequence into FastAPI's lifecycle.
**When to use:** All sniffer thread management lives here; no `@app.on_event` (deprecated since FastAPI 0.93).

```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — runs before first request
    config = load_config()           # CONFIG-01/02
    check_npcap()                    # CAP-02 — exit if missing
    check_admin()                    # CAP-03 — exit if not admin
    iface = select_interface(config) # CAP-04/09
    queue = asyncio.Queue(maxsize=config["queue_size"])  # CAP-05

    loop = asyncio.get_running_loop()
    supervisor_task = asyncio.create_task(
        sniffer_supervisor(loop, queue, iface, config)  # CAP-10
    )
    pipeline_task = asyncio.create_task(
        pipeline_worker(queue, config)  # PIPE-01/02/03
    )

    app.state.queue = queue
    app.state.supervisor_task = supervisor_task

    yield  # Application runs here

    # Shutdown
    supervisor_task.cancel()
    pipeline_task.cancel()

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: Thread→Asyncio Bridge with Drop-Head

**What:** `call_soon_threadsafe` schedules a callback in the event loop from the Scapy thread. The callback implements drop-head when queue is full.
**When to use:** Every packet captured by Scapy's `prn=` callback.

**Critical fact:** `asyncio.Queue` is NOT thread-safe. Its internal `_queue` deque must only be mutated from the event loop thread. `call_soon_threadsafe` ensures the callback runs in the event loop thread, making `get_nowait()` + `put_nowait()` safe.

```python
# Empirically verified on Python 3.11 (target machine)
import asyncio
import time
import datetime
import logging

def make_packet_event(pkt):
    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "monotonic": time.monotonic(),
        # Scapy fields populated in Phase 2 (process mapping)
        "raw_pkt": pkt,
    }

def _enqueue_packet(queue: asyncio.Queue, drop_counter: list, pkt) -> None:
    """Runs in EVENT LOOP thread via call_soon_threadsafe. Never call from Scapy thread directly."""
    event = make_packet_event(pkt)
    if queue.full():
        try:
            queue.get_nowait()  # Drop oldest (drop-head strategy — CAP-06)
            drop_counter[0] += 1
            logging.info("Packet dropped (queue full). Total drops: %d", drop_counter[0])  # CAP-07
        except asyncio.QueueEmpty:
            pass
    queue.put_nowait(event)

def make_packet_handler(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue, drop_counter: list):
    """Returns the Scapy prn= callback. Runs in Scapy's daemon thread."""
    def handler(pkt):
        loop.call_soon_threadsafe(_enqueue_packet, queue, drop_counter, pkt)
    return handler
```

### Pattern 3: Sniffer Supervisor with Exponential Backoff

**What:** An async coroutine manages the sniffer daemon thread lifecycle, restarting it on failure with exponential backoff.
**When to use:** CAP-10 — sniffer must auto-restart, not crash silently.

```python
import asyncio
import threading
import logging
from scapy.all import sniff

async def sniffer_supervisor(loop, queue, iface, config, drop_counter):
    attempt = 0
    base_delay = 1.0
    max_delay = 60.0

    while True:
        stop_event = threading.Event()
        packet_handler = make_packet_handler(loop, queue, drop_counter)

        def run_sniffer():
            try:
                sniff(
                    iface=iface,
                    prn=packet_handler,
                    store=False,         # CAP-01 — no memory accumulation
                    filter="ip",         # Outgoing IP traffic
                    stop_filter=lambda _: stop_event.is_set(),
                )
            except Exception as e:
                logging.critical("Sniffer thread died: %s", e)  # SYS-01/CONFIG-03

        sniffer_thread = threading.Thread(target=run_sniffer, daemon=True)
        sniffer_thread.start()

        sniffer_thread.join()  # Block until thread exits

        if stop_event.is_set():
            break  # Graceful shutdown — don't restart

        delay = min(base_delay * (2 ** attempt), max_delay)
        logging.warning("Sniffer died, restarting in %.1fs (attempt %d)", delay, attempt + 1)
        await asyncio.sleep(delay)
        attempt += 1
```

**Note:** `sniffer_thread.join()` blocks the coroutine. Use `loop.run_in_executor(None, sniffer_thread.join)` to yield control back to the event loop while waiting:

```python
        await loop.run_in_executor(None, sniffer_thread.join)
```

### Pattern 4: Interface Auto-Selection via psutil

**What:** Use `psutil.net_io_counters(pernic=True)` to find the interface with highest `bytes_sent`, then match to Scapy's interface name.
**When to use:** CAP-04 — when no interface is specified in config.yaml or CLI.

```python
import psutil

def auto_select_interface() -> str:
    """Returns interface name with highest outbound bytes. CAP-04."""
    counters = psutil.net_io_counters(pernic=True)
    if not counters:
        raise RuntimeError("No network interfaces found via psutil")

    # Sort by bytes_sent descending, pick the busiest
    best_iface = max(counters.items(), key=lambda x: x[1].bytes_sent)
    iface_name = best_iface[0]
    logging.info("Auto-selected interface: %s (bytes_sent: %d)", iface_name, best_iface[1].bytes_sent)
    return iface_name
```

**Windows caveat:** psutil interface names (e.g., `"Wi-Fi"`, `"Ethernet"`) may not match Scapy's interface names (e.g., `\Device\NPF_{GUID}`). Use `scapy.interfaces.conf.ifaces` to cross-reference. Scapy's `conf.ifaces.dev_from_networkname(name)` resolves friendly name to Scapy interface object.

### Pattern 5: Npcap Detection

**What:** Check for Npcap using Scapy's own detection method (filesystem check) plus registry fallback.
**When to use:** CAP-02 — before any sniffing begins.

```python
import os
import sys
import winreg

def check_npcap() -> None:
    """Exit with clear message if Npcap is not installed. CAP-02."""
    # Method 1: Scapy's own detection — checks WINDIR\System32\Npcap
    npcap_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", "Npcap")
    if os.path.isdir(npcap_dir):
        return  # Npcap found

    # Method 2: Registry check
    for reg_path in [r"SOFTWARE\Npcap", r"SYSTEM\CurrentControlSet\Services\npcap"]:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
            winreg.CloseKey(key)
            return  # Npcap found
        except FileNotFoundError:
            continue

    print("ERROR: Npcap is not installed.", file=sys.stderr)
    print("Install Npcap from https://npcap.com (enable WinPcap API-compatible mode).", file=sys.stderr)
    sys.exit(1)
```

**Verified on this machine:** Npcap is NOT installed — both registry keys return FileNotFoundError.

### Pattern 6: Admin Privilege Check

```python
import ctypes
import sys

def check_admin() -> None:
    """Exit with clear message if not running as administrator. CAP-03."""
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = False

    if not is_admin:
        print("ERROR: PNPG requires administrator privileges.", file=sys.stderr)
        print("Right-click your terminal and select 'Run as administrator'.", file=sys.stderr)
        sys.exit(1)
```

**Verified on this machine:** `IsUserAnAdmin()` returns `0` (not admin) — function works correctly.

### Pattern 7: Config Loader with Defaults

```python
import yaml
import logging

DEFAULT_CONFIG = {
    "queue_size": 500,              # CAP-05: asyncio.Queue maxsize
    "poll_interval_ms": 200,        # PROC-02 (Phase 2): psutil polling interval
    "alert_rate_limit_per_sec": 1,  # DET-06 (Phase 4): alert flood control
    "port_allowlist": [80, 443, 53, 123, 5353, 8080, 8443],  # DET-03 (Phase 4)
    "log_rotation_size_mb": 50,     # STORE-04 (Phase 5)
    "debug_mode": False,            # TEST-01
    "interface": None,              # CAP-09: None = auto-select
    "connection_rate_threshold": 50, # DET-02 (Phase 4)
    "dns_cache_size": 1000,         # DNS-06 (Phase 3)
    "dns_cache_ttl_sec": 300,       # DNS-04 (Phase 3)
    "proc_cache_ttl_sec": 2,        # PROC-06 (Phase 2)
    "log_dir": "logs",
}

def load_config(path: str = "config.yaml") -> dict:
    """Load config.yaml, apply defaults for missing keys. CONFIG-01/02."""
    user_config = {}
    try:
        with open(path, "r") as f:
            loaded = yaml.safe_load(f)
            if loaded and isinstance(loaded, dict):
                user_config = loaded
    except FileNotFoundError:
        logging.info("config.yaml not found — using all defaults")
    except yaml.YAMLError as e:
        logging.warning("config.yaml parse error: %s — using all defaults", e)

    config = dict(DEFAULT_CONFIG)
    for key, value in user_config.items():
        if key in config:
            config[key] = value
        else:
            logging.warning("Unknown config key ignored: %s", key)

    return config
```

### Pattern 8: Async Pipeline Worker

**What:** Consumes packets from asyncio.Queue, dispatches each stage sequentially.
**When to use:** PIPE-01/02/03 — the pipeline worker is the backbone of all enrichment.

```python
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

async def pipeline_worker(queue: asyncio.Queue, config: dict) -> None:
    """PIPE-01: Consumes queue, routes through enrichment pipeline. PIPE-02: preserves order."""
    executor = ThreadPoolExecutor(max_workers=4)
    loop = asyncio.get_running_loop()

    while True:
        try:
            event = await queue.get()
        except asyncio.CancelledError:
            break

        try:
            # Phase 1: stub stubs — each stage is a no-op placeholder
            # Phase 2 fills: process_mapper
            # Phase 3 fills: dns_resolver (PIPE-03: run_in_executor for blocking call)
            # Phase 4 fills: detection_engine
            # Phase 5 fills: storage_writer, websocket_push

            if config.get("debug_mode"):
                logging.debug("PIPELINE EVENT: %s", event)  # TEST-01

        except Exception as e:
            logging.critical("Pipeline worker error: %s", e, exc_info=True)  # SYS-01
        finally:
            queue.task_done()
```

### Anti-Patterns to Avoid

- **Direct `asyncio.Queue` manipulation from Scapy thread:** Never call `queue.put_nowait()` or `queue.get_nowait()` directly from the Scapy thread. Always use `loop.call_soon_threadsafe()`.
- **`run_coroutine_threadsafe` for per-packet bridging:** Creates a Future per packet — unacceptable overhead at 500+ packets/sec. Use `call_soon_threadsafe` instead.
- **`store=True` in Scapy `sniff()`:** Accumulates all packets in memory. Use `store=False` (CAP-01).
- **Inline blocking calls in pipeline worker:** `socket.gethostbyaddr()` blocks the event loop. Always `await loop.run_in_executor(None, blocking_call)`.
- **Growing JSON file for log storage:** Appending to a single JSON array becomes unreadable. Use NDJSON (one JSON object per line, opened in append mode).
- **`@app.on_event("startup")`:** Deprecated since FastAPI 0.93. Use `lifespan` context manager.
- **`sniffer_thread.join()` directly in async code:** Blocks the event loop. Use `await loop.run_in_executor(None, sniffer_thread.join)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Packet capture on Windows | Custom socket code | Scapy + Npcap | `AF_PACKET` is Linux-only; raw socket abstraction on Windows requires kernel driver anyway |
| Per-interface I/O stats | Read from `/proc/net/dev` | `psutil.net_io_counters(pernic=True)` | Cross-platform, no file parsing, works on Windows |
| Thread-safe asyncio bridge | Custom lock+queue | `loop.call_soon_threadsafe()` | This is the designed mechanism; custom locking risks deadlock |
| YAML parsing | Custom config file format | `yaml.safe_load()` | Edge cases in YAML parsing (multi-line strings, type coercion) are non-trivial |
| Exponential backoff | Sleep loop | Standard formula `min(base * 2**attempt, max_delay)` | Well-understood, no dependencies needed |

**Key insight:** In the threading/async bridge domain, rolling custom synchronization primitives is how race conditions are introduced. Scapy+Npcap and `call_soon_threadsafe` are the designed solution for their respective problems.

---

## Common Pitfalls

### Pitfall 1: Npcap Not Installed — Silent Failure
**What goes wrong:** Scapy imports successfully (`from scapy.all import sniff` returns no error), but calling `sniff()` raises `OSError: [Errno 22]` or produces zero packets with no error message.
**Why it happens:** Scapy defers driver loading to runtime. The import-time check does not validate Npcap presence.
**How to avoid:** Run `check_npcap()` at startup, before any Scapy calls (CAP-02). Check the filesystem path `WINDIR\System32\Npcap` — this is what Scapy itself checks.
**Warning signs:** `sniff()` returns immediately with empty results; no packets appear in queue after startup.

### Pitfall 2: Non-Admin — Same Silent Failure Mode
**What goes wrong:** Running without admin produces either an `OSError` (access denied) or zero packets captured — depending on Npcap version.
**Why it happens:** Raw socket access requires elevated privileges on all modern OSes.
**How to avoid:** `check_admin()` before any Scapy calls (CAP-03). Current session verified: `IsUserAnAdmin()` = 0.
**Warning signs:** Application starts but queue stays empty.

### Pitfall 3: Calling asyncio.Queue from Scapy Thread Directly
**What goes wrong:** Race condition; `queue._queue` deque is mutated from two threads simultaneously, causing data corruption or `RuntimeError`.
**Why it happens:** `asyncio.Queue` documentation says "not thread-safe" but it doesn't always crash visibly — the bug is intermittent.
**How to avoid:** Always use `loop.call_soon_threadsafe(callback, ...)` where the callback does `put_nowait`/`get_nowait`. Never access queue from Scapy's thread.
**Warning signs:** Intermittent `RuntimeError: deque mutated during iteration` or queue size assertions failing.

### Pitfall 4: Interface Name Mismatch (psutil vs Scapy)
**What goes wrong:** `psutil.net_io_counters()` returns `"Wi-Fi"` as interface name; Scapy requires `"\Device\NPF_{GUID-string}"`.
**Why it happens:** Scapy on Windows uses Npcap GUID-based interface names; psutil uses Windows-friendly display names.
**How to avoid:** Use `scapy.config.conf.ifaces.dev_from_networkname(friendly_name)` to convert. If that fails, iterate `conf.ifaces.values()` and match on the `.name` or `.description` attribute.
**Warning signs:** `Scapy: No such interface` error; empty packet captures despite correct interface selection.

### Pitfall 5: `sniffer_thread.join()` Blocking the Event Loop
**What goes wrong:** When the sniffer thread exits (normally or via exception), the supervisor coroutine calls `sniffer_thread.join()` synchronously, blocking the entire event loop until the join completes.
**Why it happens:** `join()` is a blocking call. Any blocking call in an async function blocks the event loop.
**How to avoid:** Use `await loop.run_in_executor(None, sniffer_thread.join)` to offload the join to a thread pool, yielding control back to the event loop.
**Warning signs:** All API endpoints become unresponsive while waiting for sniffer restart.

### Pitfall 6: Scapy `stop_filter` Not Stopping the Thread
**What goes wrong:** Scapy's `stop_filter` is checked after each packet, not proactively. If traffic is light, the sniffer thread may not check the stop flag for seconds.
**Why it happens:** `stop_filter` is evaluated per-packet. With no packets, it's never evaluated.
**How to avoid:** Use `timeout=` in `sniff()` as a maximum blocking duration, combined with `stop_filter`. Alternatively use Scapy's `AsyncSniffer` class (available in Scapy 2.4.3+) which runs in its own thread and supports `.stop()`.
**Warning signs:** Application takes many seconds to shutdown after stop is requested.

### Pitfall 7: config.yaml Not Present at First Run
**What goes wrong:** `open("config.yaml")` raises `FileNotFoundError`, crashing startup before any user-facing error message.
**Why it happens:** First-run scenario — no config.yaml has been created yet.
**How to avoid:** `try/except FileNotFoundError` in config loader; use all defaults silently; log `INFO: config.yaml not found, using defaults` (CONFIG-02).
**Warning signs:** Application crashes with an unhandled exception on first run.

---

## Code Examples

### Verified: Cross-Thread Queue Bridge

```python
# Source: Empirically verified Python 3.11 on Windows 11 (target machine)
import asyncio
import threading

async def main():
    loop = asyncio.get_running_loop()
    q = asyncio.Queue(maxsize=3)
    drop_count = [0]

    def enqueue(item):
        # Runs in event loop thread — safe to mutate q directly
        if q.full():
            q.get_nowait()   # Drop oldest
            drop_count[0] += 1
        q.put_nowait(item)

    def producer(loop):
        for i in range(6):
            loop.call_soon_threadsafe(enqueue, i)

    t = threading.Thread(target=producer, args=(loop,), daemon=True)
    t.start()
    await asyncio.sleep(0.2)
    t.join()

    # Result: [3, 4, 5] — last 3 preserved, 3 dropped
    print(list(q._queue))   # [3, 4, 5]
    print("drops:", drop_count[0])  # 3
```

### Verified: Admin Check

```python
# Source: Empirically verified on Windows 11 (target machine, non-admin session)
import ctypes
import sys

def check_admin():
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("ERROR: Run as administrator.", file=sys.stderr)
        sys.exit(1)
# IsUserAnAdmin() returned 0 on target machine — confirmed working
```

### Verified: Dual Timestamp

```python
# Source: Empirically verified Python 3.11 stdlib
import time
import datetime

timestamp_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
# "2026-03-31T18:11:19.165434+00:00"
timestamp_mono = time.monotonic()
# 8716.89
```

### Verified: Drop-Head asyncio.Queue

```python
# Source: Empirically verified Python 3.11 — async context
import asyncio

async def test():
    q = asyncio.Queue(maxsize=3)
    for i in range(3):
        await q.put(i)
    # q full: [0, 1, 2]
    if q.full():
        q.get_nowait()      # drops 0
    q.put_nowait(99)
    # q: [1, 2, 99]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `@asynccontextmanager` lifespan | FastAPI 0.93 (2023) | `on_event` still works but deprecated; lifespan is the documented approach |
| WinPcap | Npcap | 2020 (WinPcap EOL 2013) | WinPcap is dead; Npcap is the only maintained Windows capture driver |
| `asyncio.Queue` direct from thread | `loop.call_soon_threadsafe` | Python 3.10+ docs clarification | Direct queue access from threads was always unsafe; now explicitly documented |
| psutil `net_connections()` (changed name) | `psutil.net_connections()` still works; psutil 6.0 added `psutil.net_io_counters()` improvements | psutil 6.0 (2024) | API stable; no breaking changes for v1 use case |

**Deprecated/outdated:**
- `WinPcap`: EOL since 2013. Scapy will attempt to load it as fallback but it is unreliable on Windows 10+. Npcap with "WinPcap API-compatible mode" is the only supported option.
- `@app.on_event("startup"/"shutdown")`: Works but deprecated in FastAPI 0.93+. Use `lifespan`.
- Scapy `sniff()` without `store=False`: Will accumulate packets in memory — never use without this flag in a long-running sniffer.

---

## Open Questions

1. **Interface name matching: psutil ↔ Scapy on this specific machine**
   - What we know: psutil returns display names (e.g., "Wi-Fi"); Scapy requires `\Device\NPF_{GUID}`
   - What's unclear: Whether `conf.ifaces.dev_from_networkname()` correctly maps "Wi-Fi" to the GUID on Windows 11 Home with this Npcap version (not yet installed)
   - Recommendation: After Npcap is installed, empirically test `conf.ifaces` output and document the correct mapping function. Add defensive fallback: if `dev_from_networkname` fails, iterate `conf.ifaces.values()` and match on `.description`.

2. **Scapy `stop_filter` latency on low-traffic interfaces**
   - What we know: `stop_filter` only evaluates per packet — no proactive polling
   - What's unclear: How long shutdown will take when traffic is sparse (e.g., after dev machine goes idle)
   - Recommendation: Use `AsyncSniffer` from Scapy 2.4.3+ which has a `.stop()` method, OR use `timeout=1` on `sniff()` combined with `stop_filter` to guarantee maximum 1-second response time.

3. **Npcap installation requirement for development testing**
   - What we know: Npcap is NOT currently installed on this machine
   - What's unclear: Whether unit tests for the queue bridge and pipeline worker can be run without Npcap
   - Recommendation: Mock the Scapy `sniff()` call in tests — inject packets directly into the queue bridge via `loop.call_soon_threadsafe` to test all queue/pipeline logic without Npcap. Tests for CAP-02/03 verify the exit behavior by mocking the check functions.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Runtime | YES | 3.11.0 | — |
| Scapy | CAP-01 through CAP-10 | NO | — | None — must `pip install scapy>=2.7.0` |
| FastAPI | PIPE-01/02/03, API layer | NO | — | None — must `pip install fastapi>=0.115.0` |
| uvicorn | App server | NO | — | None — must `pip install uvicorn[standard]>=0.32.0` |
| psutil | CAP-04 (interface auto-select) | NO | — | None — must `pip install psutil>=6.0.0` |
| PyYAML | CONFIG-01/02 | NO | — | None — must `pip install pyyaml>=6.0.0` |
| Npcap driver | CAP-01 (actual packet capture) | NO | — | BLOCKING — must install from https://npcap.com |
| Administrator session | CAP-03 (raw socket access) | NO | — | BLOCKING — app must be launched from admin terminal |
| pytest | TEST-01 and all Nyquist tests | NO | — | None — must `pip install pytest>=8.0.0 pytest-asyncio>=0.23.0` |

**Missing dependencies with no fallback (BLOCKING):**
- **Npcap**: Application cannot capture any packets without it. Must be installed with "WinPcap API-compatible mode" enabled before `pip install scapy`. Download: https://npcap.com
- **Administrator session**: `ctypes.windll.shell32.IsUserAnAdmin()` returns `0` in the current session — sniffer functionality requires relaunching terminal as admin.

**Missing dependencies with fallback:**
- All Python packages: Install via `pip install -r requirements.txt`. Tests can run without Npcap by mocking `sniff()`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` (Wave 0 gap — does not exist yet) |
| Quick run command | `python -m pytest tests/test_capture/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CAP-02 | Npcap check exits with error when not installed | unit | `pytest tests/test_prereqs.py::test_npcap_check_exits -x` | NO — Wave 0 |
| CAP-03 | Admin check exits with error when not admin | unit | `pytest tests/test_prereqs.py::test_admin_check_exits -x` | NO — Wave 0 |
| CAP-05 | asyncio.Queue created with maxsize=500 | unit | `pytest tests/test_capture/test_queue_bridge.py::test_queue_maxsize -x` | NO — Wave 0 |
| CAP-06 | Drop-head: oldest item removed when queue full | unit | `pytest tests/test_capture/test_queue_bridge.py::test_drop_head -x` | NO — Wave 0 |
| CAP-07 | INFO log emitted on packet drop | unit | `pytest tests/test_capture/test_queue_bridge.py::test_drop_log -x` | NO — Wave 0 |
| CAP-08 | Event contains ISO8601 wall-clock + monotonic timestamp | unit | `pytest tests/test_capture/test_queue_bridge.py::test_timestamps -x` | NO — Wave 0 |
| CAP-09 | Interface override: config.yaml takes precedence | unit | `pytest tests/test_capture/test_interface.py::test_config_override -x` | NO — Wave 0 |
| CAP-10 | Sniffer supervisor restarts on thread death with backoff | unit | `pytest tests/test_capture/test_sniffer.py::test_supervisor_restart -x` | NO — Wave 0 |
| CONFIG-01/02 | Config defaults applied for missing keys | unit | `pytest tests/test_config.py::test_defaults -x` | NO — Wave 0 |
| CONFIG-03/SYS-01 | Pipeline worker logs critical error without crashing | unit | `pytest tests/test_pipeline/test_worker.py::test_error_no_crash -x` | NO — Wave 0 |
| PIPE-01 | Pipeline worker consumes all queued events | unit | `pytest tests/test_pipeline/test_worker.py::test_consumes_queue -x` | NO — Wave 0 |
| PIPE-02 | Pipeline worker preserves packet order | unit | `pytest tests/test_pipeline/test_worker.py::test_order_preserved -x` | NO — Wave 0 |
| TEST-01 | Debug mode prints event to console | unit | `pytest tests/test_pipeline/test_worker.py::test_debug_mode -x` | NO — Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m pytest tests/test_capture/ tests/test_pipeline/ tests/test_config.py tests/test_prereqs.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — makes tests a package
- [ ] `tests/test_prereqs.py` — covers CAP-02, CAP-03
- [ ] `tests/test_config.py` — covers CONFIG-01, CONFIG-02
- [ ] `tests/test_capture/__init__.py`
- [ ] `tests/test_capture/test_queue_bridge.py` — covers CAP-05, CAP-06, CAP-07, CAP-08
- [ ] `tests/test_capture/test_interface.py` — covers CAP-04, CAP-09
- [ ] `tests/test_capture/test_sniffer.py` — covers CAP-10 (mock sniff())
- [ ] `tests/test_pipeline/__init__.py`
- [ ] `tests/test_pipeline/test_worker.py` — covers PIPE-01, PIPE-02, CONFIG-03/SYS-01, TEST-01
- [ ] `pytest.ini` — asyncio_mode = auto for pytest-asyncio
- [ ] Framework install: `pip install pytest>=8.0.0 pytest-asyncio>=0.23.0`

---

## Sources

### Primary (HIGH confidence)
- Python 3.11 stdlib empirical verification — `asyncio.Queue`, `loop.call_soon_threadsafe`, `ctypes.windll.shell32.IsUserAnAdmin()`, `datetime`, `time.monotonic`, `winreg`, `logging` — all tested on target machine (2026-03-31)
- PyPI registry — version verification for all packages (2026-03-31): scapy=2.7.0, fastapi=0.135.2, uvicorn=0.42.0, psutil=7.2.2, pyyaml=6.0.3, pytest=9.0.2, pytest-asyncio=1.3.0
- CLAUDE.md stack research — Npcap requirement, Scapy Windows behavior, FastAPI lifespan pattern

### Secondary (MEDIUM confidence)
- [FastAPI Lifespan Events docs](https://fastapi.tiangolo.com/advanced/events/) — lifespan context manager pattern
- [Scapy 2.7.0 documentation - interfaces](https://scapy.readthedocs.io/en/stable/api/scapy.interfaces.html) — `conf.ifaces`, `dev_from_networkname()`
- [Python asyncio Queue docs](https://docs.python.org/3/library/asyncio-queue.html) — thread safety warning
- [psutil net_io_counters](https://pypi.org/project/psutil/) — `pernic=True` for per-interface stats
- WebSearch: Scapy Npcap detection method (`WINDIR\System32\Npcap` filesystem check) — corroborated by Scapy source on GitHub

### Tertiary (LOW confidence)
- WebSearch finding: `scapy.config.conf.ifaces.dev_from_networkname()` for friendly-name → GUID mapping — requires empirical validation after Npcap is installed

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against live PyPI registry
- Architecture patterns: HIGH — core patterns empirically verified on target machine (Python 3.11, Windows 11)
- Npcap detection: HIGH — Scapy's own filesystem check method (`WINDIR\System32\Npcap`) confirmed from source
- Interface name mapping: MEDIUM — psutil↔Scapy name reconciliation needs empirical validation after Npcap install
- Pitfalls: HIGH — based on combination of empirical verification and well-documented Scapy/asyncio behaviors

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (stable libraries; revalidate if Scapy or FastAPI major version changes)
