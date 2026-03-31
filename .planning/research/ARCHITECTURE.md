# Architecture Patterns

**Domain:** Local network packet-capture + process-mapping + anomaly-detection + web-dashboard
**Project:** Personal Network Privacy Guardian (PNPG)
**Researched:** 2026-03-31
**Overall confidence:** HIGH (stable Python stdlib and library patterns; verified against known library behaviors)

---

## Recommended Architecture

### System Diagram

```
 ┌──────────────────────────────────────────────────────┐
 │                  OS Kernel / Raw Sockets              │
 └────────────────────────┬─────────────────────────────┘
                          │ elevated privileges (admin/root)
                          ▼
 ┌──────────────────────────────────────────────────────┐
 │          Sniffer Thread (daemon thread)               │
 │  scapy.sniff(prn=callback, store=False)               │
 │  - blocking call, must NOT run in asyncio loop        │
 │  - filters IP + TCP/UDP outbound packets              │
 │  - callback pushes raw packet data to shared queue    │
 └────────────────────────┬─────────────────────────────┘
                          │ thread-safe queue.Queue (or asyncio.Queue via loop.call_soon_threadsafe)
                          ▼
 ┌──────────────────────────────────────────────────────┐
 │        Pipeline Worker (asyncio coroutine)            │
 │  Runs inside the FastAPI / uvicorn event loop         │
 │  Drains the queue; for each raw packet entry:         │
 │    1. Connection Extractor  → src/dst IP, port, proto │
 │    2. Process Mapper        → PID + process name      │
 │    3. DNS Resolver          → domain name (cached)    │
 │    4. Detection Engine      → alert rules applied     │
 │    5. Data Store write      → in-memory + JSON log    │
 │    6. WebSocket broadcast   → push enriched record    │
 └──────────────────────────────────────────────────────┘
                          │ async broadcast
                          ▼
 ┌──────────────────────────────────────────────────────┐
 │          FastAPI Application (main.py)                │
 │  REST endpoints:                                      │
 │    GET /connections  →  recent N records from store   │
 │    GET /alerts       →  active alert list             │
 │    GET /stats        →  aggregated counters           │
 │  WebSocket endpoint:                                  │
 │    /ws/live          →  push enriched connection JSON │
 └────────────────────────┬─────────────────────────────┘
                          │ HTTP + WebSocket (uvicorn ASGI)
                          ▼
 ┌──────────────────────────────────────────────────────┐
 │     Web Dashboard (frontend/index.html + app.js)      │
 │  - WebSocket client: receives live connection records │
 │  - Connections table: updates row-by-row              │
 │  - Alerts panel: highlights anomalies                 │
 │  - Chart.js: data-usage-per-app, conn/sec counters    │
 └──────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | File | Responsibility | Input | Output |
|-----------|------|---------------|-------|--------|
| Sniffer | `backend/sniffer.py` | Raw packet capture; OS interface | Network interface | Minimal packet dict pushed to queue |
| Analyzer | `backend/analyzer.py` | Extract src/dst IP, port, protocol from Scapy packet object | Scapy packet | `{src_ip, dst_ip, port, protocol}` |
| Process Mapper | `backend/process_mapper.py` | Match local src_ip+src_port to a PID via OS connection table | `{src_ip, src_port}` | `{pid, process_name}` |
| DNS Resolver | `backend/dns_resolver.py` | Reverse-resolve dst_ip to hostname; in-process cache | dst_ip string | domain name string or None |
| Detection Engine | `backend/detector.py` | Apply rule set; emit alerts | Enriched connection dict | `{is_alert, alert_type, severity}` |
| Data Store | `backend/data_store.py` | Thread-safe in-memory deque; async JSON log flush | Enriched record | REST query responses; JSON files |
| API / WebSocket | `backend/main.py` | FastAPI app; REST handlers; WebSocket connection manager | HTTP/WS requests | JSON responses; pushed messages |
| Frontend | `frontend/` | Browser UI; consume WS stream and REST | WS messages + REST JSON | Rendered dashboard |

**Rule:** Components communicate in one direction only (left-to-right / top-to-bottom in the pipeline). The Sniffer does not know about the API. The API does not call the Sniffer directly. The bridge is the shared queue.

---

## Data Flow Direction

```
Packet (raw bytes from OS)
  → Scapy parses → minimal dict {src_ip, src_port, dst_ip, dst_port, protocol, timestamp}
    → pushed to thread-safe queue
      → asyncio consumer drains queue
        → Analyzer extracts fields (already in dict from sniffer callback)
          → Process Mapper enriches: adds {pid, process_name}
            → DNS Resolver enriches: adds {domain}
              → Detection Engine enriches: adds {alerts:[]}
                → Data Store: appends to in-memory deque, async-writes to JSON log
                  → WebSocket Manager broadcasts to all connected clients
                    → Frontend receives JSON record, updates table + charts
```

DNS and process-name lookup results are cached so repeated lookups for the same IP or port combo do not block the pipeline.

---

## Threading and Async Model

### The Core Problem

`scapy.sniff()` is a **blocking call**. It runs a C-level select/recv loop internally. It cannot be awaited. Placing it inside an `async def` function or running it on the asyncio event loop would block all async operations (FastAPI request handling, WebSocket sends, etc.).

### The Solution: Dedicated Daemon Thread + asyncio Queue Bridge

**Confidence: HIGH** — this is the standard pattern for integrating blocking I/O with asyncio in Python.

```
Thread A (sniffer daemon thread)
  scapy.sniff(prn=_packet_callback, store=False, ...)

def _packet_callback(pkt):
    # This runs in Thread A
    # Build minimal dict — keep this cheap
    record = extract_minimal(pkt)
    # Bridge to asyncio: thread-safe handoff
    asyncio.run_coroutine_threadsafe(
        _async_queue.put(record),
        loop=_event_loop
    )

Thread B (uvicorn event loop)
  async def pipeline_worker():
      while True:
          record = await _async_queue.get()
          enriched = await enrich(record)  # process map, DNS, detect
          data_store.append(enriched)
          await ws_manager.broadcast(enriched)
```

**Critical implementation details:**

1. The asyncio event loop reference must be captured **before** spawning the sniffer thread, and passed to it or stored at module level.
2. `asyncio.run_coroutine_threadsafe()` is the correct bridge — it is thread-safe. Do NOT call `loop.call_soon()` from another thread (not thread-safe).
3. `scapy.sniff()` should use `store=False` to prevent unbounded memory growth — packets are processed by callback, not accumulated.
4. The sniffer thread must be started as a `daemon=True` thread so it does not prevent clean process exit.
5. The FastAPI lifespan (`@asynccontextmanager` lifespan event, preferred over deprecated `on_event`) is where the sniffer thread and pipeline worker are started.

### Alternative: asyncio.Queue with loop.call_soon_threadsafe

```python
# Equivalent — slightly simpler for put_nowait use cases
loop.call_soon_threadsafe(queue.put_nowait, record)
```

This avoids creating a coroutine object per packet, which is cheaper at high packet rates. Recommended for production use in this project.

### DNS Resolution: run_in_executor

`socket.gethostbyaddr()` is a **blocking system call** (it may make a network request to the local DNS server). It must NOT be called directly in an async function.

```python
# Correct pattern
async def resolve_dns(ip: str) -> str | None:
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
        return result[0]
    except socket.herror:
        return None
```

`run_in_executor` dispatches the blocking call to the default ThreadPoolExecutor, freeing the event loop.

**Cache requirement:** DNS lookups are slow (10-100ms). Maintain an in-process `dict[str, str]` TTL cache (IP → domain). Without caching, high-traffic periods will saturate the thread pool with duplicate DNS queries.

### Process Mapper: Synchronous but Fast

`psutil.net_connections()` is synchronous but typically completes in under 5ms on desktop systems (it reads `/proc/net/tcp` on Linux or calls `GetExtendedTcpTable` on Windows). It can be called directly in async context without `run_in_executor` for low packet rates, but for correctness and to avoid periodic stalls, wrap it:

```python
async def map_process(src_ip: str, src_port: int) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_map_process, src_ip, src_port)
```

**Cache requirement:** psutil.net_connections() rebuilds the full table on each call. Cache results for 500ms–1s per (src_ip, src_port) pair to avoid calling it for every packet.

---

## How psutil Correlation Works at the OS Level

### The Fundamental Gap

Scapy operates at the **libpcap/npcap layer** — it sees raw packets as they pass through the network interface. Packets contain source IP + source port (layer 3/4 headers) but carry **no process identifier**. The OS kernel knows which process owns which socket, but that information is stripped before the packet reaches libpcap.

### The Correlation Mechanism

```
Scapy packet:  src_ip=192.168.1.5, src_port=51234, dst_ip=142.250.183.14, dst_port=443

psutil.net_connections() returns a list of all current OS sockets:
  [
    sconn(fd=23, family=AF_INET, type=SOCK_STREAM,
          laddr=addr(ip='192.168.1.5', port=51234),
          raddr=addr(ip='142.250.183.14', port=443),
          status='ESTABLISHED', pid=8412),
    ...
  ]

Correlation: match packet.src_port == conn.laddr.port
             (and optionally packet.src_ip == conn.laddr.ip for multi-NIC hosts)
             → conn.pid = 8412 → psutil.Process(8412).name() = "chrome.exe"
```

### Timing Race Condition

The connection table is a point-in-time snapshot. By the time `psutil.net_connections()` is called, the connection may have been closed (short-lived UDP DNS queries, brief TCP connections). Strategy:

1. **Poll the connection table proactively** in a background task (every 100-500ms) and maintain an in-memory map of `(laddr_ip, laddr_port) → pid`. Packets are then correlated against this cached map rather than triggering a fresh psutil call per packet.
2. On cache miss, attempt one live psutil call (tolerate failure — process may have exited).
3. Mark unmapped connections as `process: "unknown"` rather than dropping them.

### Platform Notes

| Platform | psutil data source | Notes |
|----------|-------------------|-------|
| Linux | `/proc/net/tcp`, `/proc/net/tcp6`, `/proc/net/udp` | Fast; requires root for PID column |
| Windows | `GetExtendedTcpTable` (iphlpapi.dll) | Requires admin for PID |
| macOS | `netstat` / `lsof` internally | Slower than Linux |

On Windows: Scapy requires **Npcap** (not WinPcap) for Windows 10/11 compatibility.

---

## Patterns to Follow

### Pattern 1: ConnectionManager for WebSocket Broadcast

Maintain a set of active WebSocket connections and broadcast to all:

```python
class ConnectionManager:
    def __init__(self):
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, data: dict):
        disconnected = set()
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)
        self.active -= disconnected
```

**Why:** Failed sends (client disconnected) must not crash the broadcast loop. Discard dead connections silently.

### Pattern 2: Enriched Record as Immutable Dict

Each stage of the pipeline returns a new dict rather than mutating in place (immutability principle):

```python
# Analyzer produces:
base = {"src_ip": ..., "dst_ip": ..., "port": ..., "protocol": ..., "timestamp": ...}

# Process mapper returns NEW dict:
with_process = {**base, "pid": 8412, "process_name": "chrome.exe"}

# DNS resolver returns NEW dict:
with_dns = {**with_process, "domain": "google.com"}

# Detector returns NEW dict:
final = {**with_dns, "alerts": [], "severity": "normal"}
```

### Pattern 3: Lifespan for Startup/Shutdown

FastAPI's lifespan context manager (not deprecated `on_event`) manages background tasks:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    loop = asyncio.get_event_loop()
    sniffer_thread = threading.Thread(
        target=start_sniffer, args=(loop, packet_queue), daemon=True
    )
    sniffer_thread.start()
    worker_task = asyncio.create_task(pipeline_worker(packet_queue))
    poller_task = asyncio.create_task(connection_table_poller())
    yield
    # Shutdown
    worker_task.cancel()
    poller_task.cancel()

app = FastAPI(lifespan=lifespan)
```

### Pattern 4: Bounded Deque for In-Memory Store

Use `collections.deque(maxlen=N)` rather than an unbounded list:

```python
from collections import deque

connections: deque[dict] = deque(maxlen=1000)
alerts: deque[dict] = deque(maxlen=500)
```

This prevents unbounded memory growth during long monitoring sessions. REST endpoints return `list(connections)` snapshots.

### Pattern 5: JSON Log with Async File Writes

Accumulate records in memory; flush to JSON file periodically (every N records or every T seconds) using `asyncio.create_task` with a flush coroutine. Do not write to disk on every packet — disk I/O would become the bottleneck at high packet rates.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Running scapy.sniff() in an async def

**What:** `async def start(): scapy.sniff(...)`

**Why bad:** Blocks the entire asyncio event loop. FastAPI cannot handle HTTP requests, WebSocket sends stall, all async tasks freeze.

**Instead:** Dedicated daemon thread as described above.

### Anti-Pattern 2: Calling socket.gethostbyaddr() Directly in Async Context

**What:** `domain = socket.gethostbyaddr(ip)` inside `async def`

**Why bad:** Blocking DNS call stalls the event loop for the duration of the DNS round-trip (potentially 50-500ms).

**Instead:** `await loop.run_in_executor(None, socket.gethostbyaddr, ip)` with TTL cache.

### Anti-Pattern 3: Calling psutil.net_connections() Per Packet Without Caching

**What:** Fresh psutil call for every packet in the pipeline

**Why bad:** At 1000 packets/second, psutil rebuilds the full OS connection table 1000 times per second. On Windows this involves kernel API calls that can take 5-20ms each.

**Instead:** Background poller task refreshes the table every 200-500ms; pipeline does a dict lookup.

### Anti-Pattern 4: Storing Full Scapy Packet Objects in the Queue

**What:** Push the raw Scapy `Packet` object through the queue to the asyncio side

**Why bad:** Scapy packet objects hold references to internal packet parsing state; they are large and not designed for cross-thread sharing. Causes unpredictable memory use.

**Instead:** Extract only the needed fields (5-tuple + timestamp) in the sniffer callback before enqueuing.

### Anti-Pattern 5: Unbounded asyncio Queue

**What:** `asyncio.Queue()` with no maxsize

**Why bad:** During traffic bursts, the queue grows unboundedly. The pipeline worker cannot drain it fast enough (DNS lookups + psutil calls are slow). Memory use climbs until OOM.

**Instead:** `asyncio.Queue(maxsize=500)`. In the sniffer callback, use `put_nowait` and catch `asyncio.QueueFull` — drop the packet and increment a `dropped_packets` counter visible in `/stats`. Dropping is acceptable; unbounded memory growth is not.

---

## Scalability Considerations

| Concern | At normal traffic (~100 pkt/s) | At burst (~1000 pkt/s) | Mitigation |
|---------|-------------------------------|------------------------|------------|
| psutil cost | Negligible with polling | Saturates without cache | 200ms polling cache |
| DNS latency | Manageable | Executor pool saturated | TTL cache (most IPs repeat) |
| WebSocket clients | Single client, fine | N/A (local tool) | Bounded broadcast |
| JSON log writes | Per-packet: fine | Per-packet: disk bottleneck | Batch flush every 100 records |
| Queue depth | Rarely fills | Can overflow | maxsize=500, drop+count |
| Memory (connections store) | Small | Large | deque maxlen=1000 |

---

## Suggested Build Order

The build order reflects strict data-dependency: each layer requires the layer below it to be working before integration is meaningful.

```
Phase 1: Packet Capture (sniffer.py)
  └─ Verify: Scapy captures packets; threading model works; queue receives entries

Phase 2: Process Mapping (process_mapper.py + connection_table_poller)
  └─ Requires: Phase 1 produces (src_ip, src_port) tuples
  └─ Verify: Packet entries gain {pid, process_name}

Phase 3: DNS Resolution (dns_resolver.py with cache)
  └─ Requires: Phase 1 produces dst_ip
  └─ Verify: Packet entries gain {domain}; cache hit rate confirmed

Phase 4: Detection Engine (detector.py)
  └─ Requires: Phase 2 (process_name for "unknown process" rule)
               Phase 3 (domain for "no DNS" rule)
  └─ Verify: Alert objects generated for known-bad patterns

Phase 5: Data Store + Pipeline Worker (data_store.py + pipeline in main.py)
  └─ Requires: Phases 1-4 all produce correct enriched dicts
  └─ Verify: In-memory deque fills; JSON log written; REST endpoints return data

Phase 6: FastAPI REST + WebSocket (main.py endpoints + lifespan)
  └─ Requires: Phase 5 data store is populated
  └─ Verify: curl /connections returns JSON; /ws/live streams records

Phase 7: Frontend Dashboard (frontend/)
  └─ Requires: Phase 6 WebSocket and REST working
  └─ Verify: Live table updates; alerts render; charts update
```

**Rationale for this order:**
- Phases 1-4 can be developed and tested with Python scripts alone — no FastAPI needed.
- The API (Phase 6) is only glue; it must not be built before the pipeline it exposes exists.
- The frontend (Phase 7) is pure consumer and has zero implementation risk once the WebSocket contract is stable.
- Process mapping (Phase 2) and DNS (Phase 3) are independent of each other — they can be developed in parallel and integrated in Phase 4.

---

## Component Communication Summary

```
sniffer.py        →  (thread-safe queue)  →  pipeline worker (in main.py)
pipeline worker   →  analyzer.py          →  dict with {src,dst,port,protocol}
pipeline worker   →  process_mapper.py    →  dict enriched with {pid, process_name}
pipeline worker   →  dns_resolver.py      →  dict enriched with {domain}
pipeline worker   →  detector.py          →  dict enriched with {alerts}
pipeline worker   →  data_store.py        →  deque append + JSON flush
pipeline worker   →  ws_manager.broadcast →  all connected WebSocket clients
main.py REST      →  data_store.py        →  read-only snapshot (list())
frontend app.js   →  /ws/live             →  receive pushed JSON records
frontend app.js   →  GET /connections     →  initial page load data
frontend app.js   →  GET /alerts         →  alerts panel
frontend app.js   →  GET /stats          →  chart data
```

No component calls backwards up the chain. The data store is the only shared state accessed from both the pipeline worker (write) and the REST handlers (read) — this access must be protected with an `asyncio.Lock` since both run on the same event loop.

---

## Sources

- Python threading + asyncio bridge: `asyncio.run_coroutine_threadsafe` — Python 3.10 stdlib documentation (HIGH confidence; stable since Python 3.4.4)
- Scapy `sniff()` blocking behavior and `store=False` parameter: Scapy official documentation (HIGH confidence)
- psutil `net_connections()` and PID correlation: psutil documentation and `/proc/net/tcp` Linux kernel ABI (HIGH confidence; behavior stable across psutil 5.x+)
- FastAPI lifespan context manager (replaces deprecated `on_event`): FastAPI official docs 0.95+ (HIGH confidence)
- FastAPI WebSocket ConnectionManager pattern: FastAPI official documentation example (HIGH confidence)
- `socket.gethostbyaddr` blocking behavior: Python socket module documentation (HIGH confidence)
- `asyncio.Queue` maxsize behavior: Python asyncio documentation (HIGH confidence)
- Npcap requirement for Scapy on Windows 10/11: Scapy Windows documentation (HIGH confidence)
- `collections.deque(maxlen=N)` for bounded ring buffer: Python collections documentation (HIGH confidence)
