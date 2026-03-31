# Technology Stack

**Project:** Personal Network Privacy Guardian (PNPG)
**Researched:** 2026-03-31
**Research note:** External network tools (WebFetch, WebSearch, Bash) were unavailable during this session. Findings are drawn from training data (knowledge cutoff August 2025) supplemented by Context7 MCP availability. Confidence levels reflect this limitation explicitly.

---

## Recommended Stack

### Core Capture Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ (use 3.11 or 3.12) | Runtime | 3.11 delivers ~25% speed improvement over 3.10 via specializing adaptive interpreter; 3.12 adds further optimizations. 3.10 is the floor but 3.11+ is preferred for the sniff-loop performance. |
| Scapy | 2.5.x (latest stable) | Packet capture and packet parsing | De facto standard for Python packet manipulation. Built-in BPF filter support. No viable pure-Python alternative for raw socket capture at this abstraction level. |
| Npcap | 1.79+ (latest) | Windows packet capture driver (required by Scapy on Windows) | WinPcap is **dead** (last released 2013, EOL). Npcap is the maintained successor. Scapy on Windows will not function without it. Install with "WinPcap API-compatible mode" enabled. |

**Confidence — Python version:** HIGH (well-established performance data)
**Confidence — Scapy version:** MEDIUM (version number from training data; validate against PyPI at install time)
**Confidence — Npcap requirement:** HIGH (Scapy docs have required Npcap on Windows since ~2019; this is not in question)

---

### Process Mapping Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| psutil | 5.9.x or 6.x | Map network connections to PIDs and process names | The only mature cross-platform library for this. `net_connections()` is the exact API needed to correlate local IP+port pairs from Scapy captures to OS-level process information. |

**Confidence — psutil:** HIGH (stable, long-standing library; API has not changed materially in years)

**Windows-specific psutil note:** On Windows, `psutil.net_connections()` requires either elevated privileges (Administrator) or — in some cases — the `PROCESS_QUERY_INFORMATION` right. Running the entire backend as Administrator (which Scapy already requires) satisfies this. Do not expect `net_connections()` to work from a non-elevated process on Windows.

**psutil API warning (MEDIUM confidence):** In psutil 6.0, `net_connections()` was renamed to `net_connections()` with some parameter changes. Validate the exact method signature against the installed version at build time. The pattern `psutil.net_connections(kind='inet')` should be used rather than the bare call.

---

### DNS Resolution Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| socket (stdlib) | Python stdlib | Reverse DNS lookup | `socket.gethostbyaddr(ip)` is synchronous and blocks. This is acceptable only if DNS calls are dispatched to a thread pool (see Architecture notes below). No third-party library needed for v1. |

**Confidence:** HIGH

**Critical warning:** `socket.gethostbyaddr()` is **blocking**. Calling it inline in the sniff callback will stall packet processing under any meaningful traffic load. The correct pattern is to dispatch DNS resolution to `asyncio.get_event_loop().run_in_executor(None, socket.gethostbyaddr, ip)` or use a `ThreadPoolExecutor`. This must be architecturally enforced from day one — retrofitting is painful.

**Alternative to consider (LOW confidence — not validated):** `dnspython` (library `dns.resolver`) offers async-aware DNS resolution and a TTL-aware cache. For v1 with the constraint of no extra dependencies this is overkill, but it is the upgrade path if `socket.gethostbyaddr` proves too slow.

---

### Backend API Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.110.x–0.115.x | REST API + WebSocket server | Correct choice. Async-native, built-in WebSocket via Starlette, auto OpenAPI docs, minimal boilerplate. The `WebSocket` class in FastAPI handles the `/ws/live` endpoint cleanly. |
| uvicorn | 0.29.x–0.32.x | ASGI server | The standard pairing for FastAPI. Use `uvicorn[standard]` to pull in `websockets` and `httptools` for better performance. |
| websockets | 12.x (pulled by uvicorn[standard]) | WebSocket protocol implementation | Pulled in transitively; do not pin separately. |

**Confidence — FastAPI:** HIGH (dominant async Python framework; versions cited are from training data, validate against PyPI)
**Confidence — uvicorn:** HIGH

**FastAPI + Scapy threading model (CRITICAL):** Scapy's `sniff()` is **blocking** and must run in a separate thread. The canonical pattern is:

```python
import threading
from scapy.all import sniff

def start_sniffer():
    thread = threading.Thread(target=sniff, kwargs={
        "filter": "ip",
        "prn": packet_callback,
        "store": False
    }, daemon=True)
    thread.start()
```

The FastAPI app's `lifespan` context manager (introduced in FastAPI 0.93 as the replacement for deprecated `on_event` startup handlers) is the correct hook for launching this thread. Using `@app.on_event("startup")` still works but is deprecated in favor of `lifespan`.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_sniffer()
    yield
    # cleanup if needed

app = FastAPI(lifespan=lifespan)
```

**Confidence — lifespan pattern:** HIGH (documented FastAPI behavior as of 0.93+)

---

### Frontend Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Vanilla HTML/CSS/JS | — | UI shell | Correct for this scope. No framework needed; adding React/Vue would add build tooling complexity with zero benefit for a single-page local tool. |
| Chart.js | 4.x | Data visualization (connections/sec, per-app usage) | The right choice. Lightweight, zero-dependency CDN delivery, well-documented canvas-based charts. Version 4.x (not 3.x) — breaking changes between 3 and 4 include dataset configuration structure. Use CDN: `https://cdn.jsdelivr.net/npm/chart.js@4`. |
| Bootstrap | 5.3.x (optional) | UI component styling | Listed as optional in PRD. Use it — the time savings on table/alert styling are real and the CDN delivery keeps zero build steps. Bootstrap 5 (not 4) — no jQuery dependency. |
| Native WebSocket API | Browser built-in | Real-time connection to `/ws/live` | Correct. The browser `WebSocket` constructor is all that is needed; no `socket.io` or similar library required. |

**Confidence — Chart.js 4:** HIGH
**Confidence — Bootstrap 5:** HIGH

---

### Data Storage Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python in-memory list/dict | stdlib | Live connection buffer | Correct for v1. A `collections.deque(maxlen=N)` is better than a plain list for bounded circular logging — prevents unbounded memory growth under sustained traffic. |
| JSON flat files | stdlib `json` module | Persistent log of connections and alerts | Correct for v1. Use append-mode logging with rotation logic or a size cap — naively growing a single JSON file will become unreadable quickly. Recommend writing newline-delimited JSON (NDJSON) rather than a single array, so log readers don't need to parse the entire file. |

**Confidence:** HIGH (stdlib, no version concerns)

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Packet capture | Scapy | pypcap / dpkt | pypcap is thinner but lacks Scapy's packet dissection; dpkt is read-only for pcap files. Scapy is the right tool when you need live capture + parsing in one library. |
| Packet capture (Windows alt) | Scapy + Npcap | Raw sockets (socket.AF_PACKET) | `AF_PACKET` is Linux-only; does not exist on Windows. Never use this for a Windows target. |
| Process mapping | psutil | WMI (Windows-only) | WMI is Windows-only and requires `pywin32` or `wmi` packages. psutil is cross-platform and has identical API on Windows/Linux. |
| DNS resolution | socket stdlib | dnspython | dnspython adds a dependency for marginal gain in v1. stdlib socket is adequate if properly threaded. |
| Backend framework | FastAPI | Flask | Flask is sync-first; WebSocket support requires `flask-socketio` + `gevent`, adding complexity. FastAPI's native async + WebSocket is cleaner. |
| Backend framework | FastAPI | aiohttp | aiohttp is capable but has weaker DX, no auto-docs, and less ecosystem momentum in 2024-2025. |
| ASGI server | uvicorn | hypercorn | uvicorn is the de facto standard for FastAPI; hypercorn is viable but less tested with FastAPI's WebSocket layer. |
| Charts | Chart.js | D3.js | D3 is far more powerful but the learning curve is steep for a lab project. Chart.js covers bar, line, and doughnut charts needed here with minimal code. |
| Charts | Chart.js | Plotly.js | Plotly is larger (3x the bundle size), better for scientific plots. Overkill for connections/sec and per-app usage. |
| Frontend | Vanilla JS | React/Vue | Build tooling (Vite/webpack) adds complexity for zero benefit in a single-page local tool served from the filesystem. Vanilla JS with WebSocket is 20 lines. |

---

## Windows-Specific Considerations

These are the highest-risk platform issues for this project on Windows 11 (the stated target):

### 1. Npcap is a hard prerequisite — not optional

Scapy on Windows delegates all raw packet capture to the WinPcap/Npcap driver layer. Without Npcap installed:
- `from scapy.all import sniff` will succeed (import works)
- Calling `sniff()` will raise `OSError: [Errno 22] Invalid argument` or fail silently with no packets captured

**Action:** Add a startup check that calls `conf.use_npcap` or attempts to list interfaces via `get_if_list()` before the application starts. Fail fast with a clear error message: "Npcap not found. Install Npcap from https://npcap.com with WinPcap API-compatible mode enabled."

**Confidence:** HIGH

### 2. Administrator elevation is mandatory — handle gracefully

Scapy requires raw socket access. On Windows, this means the process must run elevated. A common failure mode is the application appearing to start normally but capturing zero packets.

**Action:** Check `ctypes.windll.shell32.IsUserAnAdmin()` at startup and exit with a clear message if not elevated.

**Confidence:** HIGH

### 3. Interface selection on Windows differs from Linux

On Linux, `sniff(iface="eth0")` uses predictable interface names. On Windows, Scapy uses GUID-based interface names like `\Device\NPF_{GUID}`. Running `scapy.all.get_if_list()` will return these GUIDs, not human-readable names.

**Action:** At startup, enumerate interfaces and either auto-select the default route interface or expose a config option. Use `scapy.all.conf.iface` to get/set the default interface.

**Confidence:** HIGH

### 4. BPF filter behavior differs between Windows and Linux

On Linux, Scapy compiles BPF filters in the kernel. On Windows via Npcap, BPF filtering happens in userspace. The filter syntax is the same, but performance characteristics differ — complex filters are slower on Windows.

**Recommended filter:** `"ip and (tcp or udp)"` — simple enough that this performance difference is negligible.

**Confidence:** MEDIUM (documented behavior, but specific performance numbers not validated)

### 5. psutil elevation dependency on Windows

`psutil.net_connections()` on Windows may return partial results or raise `AccessDenied` for some entries even when run as Administrator, depending on whether certain system processes restrict access to their handles.

**Action:** Wrap each `net_connections()` call in a try/except and treat `psutil.AccessDenied` as a soft failure — log the PID as "unknown process" rather than crashing.

**Confidence:** MEDIUM (documented psutil behavior; specific Windows version edge cases may vary)

---

## Installation

```bash
# Core backend
pip install "fastapi>=0.110.0"
pip install "uvicorn[standard]>=0.29.0"
pip install "scapy>=2.5.0"
pip install "psutil>=5.9.0"

# No additional packages needed for v1
```

**Windows prerequisite (NOT pip):** Install Npcap from https://npcap.com — download the installer, run as Administrator, check "WinPcap API-compatible mode".

**Minimal requirements.txt:**
```
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
scapy>=2.5.0
psutil>=5.9.0
```

**Frontend (CDN, no npm):**
```html
<!-- Chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>

<!-- Bootstrap (optional) -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
```

---

## PRD Validation — What to Keep, What to Change

| PRD Decision | Verdict | Notes |
|--------------|---------|-------|
| Scapy for packet capture | KEEP | Correct. No better alternative for this use case. |
| psutil for process mapping | KEEP | Correct. Wrap in try/except for AccessDenied on Windows. |
| socket for DNS | KEEP with caveat | Must be run off the main thread. This is not optional — inline blocking DNS calls will stall the sniffer. |
| FastAPI | KEEP | Correct. Use `lifespan` not `on_event` for startup. |
| uvicorn | KEEP | Use `uvicorn[standard]` not bare `uvicorn` to include websockets dependency. |
| HTML/JS frontend | KEEP | Correct for scope. |
| Chart.js | KEEP | Specify version 4.x, not 3.x. |
| Bootstrap optional | RECOMMEND USING IT | Time savings on table/alert styling justify the CDN line. Zero build complexity. |
| JSON flat file storage | KEEP | Use NDJSON (newline-delimited) not a single growing JSON array. Use `collections.deque` for in-memory buffer. |
| No SQLite v1 | KEEP | Correct deferral. |
| requirements.txt without versions | CHANGE | Pin minimum versions (`>=`) to avoid pulling in breaking changes. |

---

## Confidence Assessment Summary

| Area | Confidence | Reason |
|------|------------|--------|
| Scapy (core capability) | HIGH | Stable, well-documented library; behavior on Windows is well-known |
| Scapy version number | MEDIUM | Cited from training data; validate against PyPI at install |
| Npcap Windows requirement | HIGH | Documented hard requirement; WinPcap has been EOL since 2013 |
| FastAPI/uvicorn versions | MEDIUM | Cited from training data; validate against PyPI at install |
| FastAPI lifespan pattern | HIGH | Documented API change with stable behavior since 0.93 |
| psutil Windows behavior | MEDIUM | Core behavior HIGH; edge cases around AccessDenied are MEDIUM |
| Chart.js v4 | HIGH | Version 4 released 2022; breaking changes from v3 are documented |
| DNS threading requirement | HIGH | Fundamental async/sync interop concern, not version-dependent |
| Windows interface naming | HIGH | Persistent GUID-based naming is a long-standing Scapy/Windows behavior |

---

## Sources

- Training data (knowledge cutoff August 2025): FastAPI docs, Scapy official docs, psutil changelog, uvicorn releases
- Note: External sources (PyPI, official documentation sites) were unavailable during this research session due to tool permission restrictions. Version numbers cited as MEDIUM confidence should be validated against PyPI before pinning in requirements.txt.
- Validate Scapy current version: https://pypi.org/project/scapy/
- Validate FastAPI current version: https://pypi.org/project/fastapi/
- Validate uvicorn current version: https://pypi.org/project/uvicorn/
- Validate psutil current version: https://pypi.org/project/psutil/
- Npcap (Windows driver): https://npcap.com
