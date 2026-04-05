# Phase 5: Data Store and Backend API - Research

**Researched:** 2026-04-05
**Domain:** PostgreSQL/asyncpg, FastAPI REST + WebSocket, JWT auth, NDJSON audit logs
**Confidence:** HIGH

---

## Summary

Phase 5 wires the completed pipeline (Phases 1-4) into persistent storage and a versioned HTTP API. Three interconnected workstreams must be sequenced carefully: (1) the PostgreSQL schema and NDJSON writer must exist before the pipeline writes to them; (2) JWT auth must be in place before REST endpoints are exposed; (3) the WebSocket manager depends on both the DB layer (it reads from it for reconnect replay) and the pipeline worker (which feeds it live events).

The critical integration point is `worker.py` lines 79-80: two stub comments (`# Phase 5: storage_writer(event)` and `# Phase 5: websocket_push(event)`) mark exactly where Phase 5 hooks in. Everything new slots in after `detect_event()` and before `debug_mode` logging. No existing code needs structural change — only extension.

`app.state` already carries `config`, `detector_state`, `probe_type`, `drop_counter`, and `stop_event`. Phase 5 adds `db_pool`, `ws_manager`, and `ndjson_writer` to `app.state`, all initialized in the lifespan and consumed by route handlers and the worker via dependency injection.

**Primary recommendation:** Use `asyncpg` (connection pool) for all DB writes from the pipeline worker and route handlers. Use `psycopg3` (already installed, v3.3.2) only as a fallback or for schema migration scripts where sync is acceptable. For JWT, use `python-jose[cryptography]` + `passlib[bcrypt]`. For rate limiting, use `slowapi`. For WebSocket batch delivery, implement a custom manager with `asyncio.Queue` per client and a background `asyncio.Task` running the 500ms timer — do not use a third-party WS library.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STORE-01 | Connection events persisted to PostgreSQL `connections` table; 30-day retention | asyncpg pool insert; nightly APScheduler purge |
| STORE-02 | Alert events persisted to PostgreSQL `alerts` table; 90-day retention | Same pool; separate table |
| STORE-03 | `processes` registry table tracks process name, path, first_seen, last_seen | UPSERT ON CONFLICT pattern |
| STORE-04 | `allowlist` table stores user-defined allow rules | CRUD via REST endpoints |
| STORE-05 | Connection events also written to `logs/connections.ndjson` | Buffered async file writer |
| STORE-06 | Alert events also written to `logs/alerts.ndjson` | Same writer, separate file |
| STORE-07 | NDJSON logs rotate/cap at configurable size | Check file size before each append; rotate on exceed |
| STORE-08 | Each connection event has unique `event_id` (UUID) | Already present in pipeline event dict |
| STORE-09 | Each event has `severity` field | Already set by detector |
| STORE-10 | DB indexes on `connections(timestamp, process_name)`, `connections(dst_ip)`, `alerts(timestamp, severity)` | DDL in schema migration |
| STORE-11 | Nightly purge of data outside retention window | APScheduler `AsyncIOScheduler` at 02:00 |
| AUTH-01 | POST /api/v1/auth/login returns JWT (HS256, 8h) + refresh token | python-jose; passlib bcrypt verify |
| AUTH-02 | All REST endpoints require valid JWT; 401 if missing/invalid | FastAPI `Depends(get_current_user)` |
| AUTH-03 | WebSocket authenticates via `?token=<jwt>` query param | Extract from `websocket.query_params` before accept |
| AUTH-04 | Password stored as bcrypt hash; first-run setup wizard | Write hash to `data/auth.json` on first run |
| API-01 | GET /api/v1/connections — paginated, filterable | asyncpg SELECT with WHERE + LIMIT/OFFSET |
| API-02 | GET /api/v1/alerts — paginated, filterable by status/severity | Same pattern |
| API-03 | GET /api/v1/stats/summary — 24h aggregates | Single SQL query with COUNT/GROUP BY |
| API-04 | GET /api/v1/stats/timeseries — bucketed metrics | `date_trunc` / `time_bucket` SQL |
| API-05 | GET /api/v1/status — capture state, interface, uptime, probe type | Reads `app.state` fields |
| API-06 | WebSocket /api/v1/ws/live — 500ms batching, 10s heartbeat | Custom WsManager with asyncio.Task |
| API-07 | WebSocket client filter messages `{ "type": "filter", ... }` | Per-client filter dict in WsManager |
| API-08 | WebSocket handles disconnections without crashing broadcast loop | Try/except around each client send |
| API-09 | FastAPI lifespan (not deprecated on_event) | Already in place — extend only |
| API-10 | WS batches capped at 100 events; slow clients dropped | Deque maxlen=100 per client |
| API-11 | Rate limiting: 100 REST req/min per client | slowapi `Limiter` on router |
| API-12 | GET /api/v1/health — status, probe type, db status, stream status | Probe asyncpg pool; check worker running |
| API-13 | Consistent envelope `{ "data": ..., "pagination": ... }` for list responses | Pydantic response models |
| ALLOW-05 | Allowlist rules persist in PostgreSQL | allowlist table; DetectorState.allowlist synced on writes |
| ALLOW-06 | GET /allowlist, POST /allowlist, DELETE /allowlist/:rule_id | Standard CRUD handlers |
| SUPP-03 | Suppressions persisted in PostgreSQL | `suppressions` table |
| SUPP-05 | PATCH /api/v1/alerts/:alert_id with action suppress/resolve | Update `alerts.status` column |
| OBS-04 | Log packets/sec, drops, active connection count every 5 seconds | APScheduler job reading `app.state.drop_counter` |
| SYS-02 | Graceful shutdown flushes in-memory data to disk before exit | lifespan shutdown block: await ndjson_writer.flush() |
| SYS-04 | If PostgreSQL unavailable, API returns 503; events queue in stream until recovery | Pool `connect_timeout`; health endpoint; queue buffer |
| TEST-02 | Synthetic load generator for PERF-01/02 testing | `asyncio.gather` HTTP client script |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncpg | 0.31.0 | PostgreSQL async driver | Native asyncio, no thread overhead, 3-5x faster than psycopg2 for async workloads; pool built-in |
| psycopg3 | 3.3.2 (already installed) | Schema migrations, sync admin scripts | Already present; use for DDL/migration scripts where sync is fine |
| python-jose[cryptography] | 3.5.0 | JWT encode/decode (HS256) | Most widely used Python JWT lib; cryptography backend required for HS256 |
| passlib[bcrypt] | 1.7.4 + bcrypt 5.0.0 | Password hashing | passlib provides stable API; bcrypt 5.x is latest backend |
| slowapi | 0.1.9 | Rate limiting for FastAPI | Limiter wraps starlette; integrates with FastAPI middleware; minimal boilerplate |
| python-multipart | 0.0.22 | Form parsing (login endpoint) | Required by FastAPI for OAuth2PasswordRequestForm or form body |
| APScheduler | 3.11.2 | Nightly purge + OBS-04 periodic metric logging | AsyncIOScheduler runs inside existing event loop; no extra thread |
| httpx | 0.28.1 | Test client for FastAPI endpoints (TestClient async) | `AsyncClient` used in tests; already in ecosystem |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | 1.3.0 (installed) | Async test support | All async route and DB tests |
| anyio | (pulled by FastAPI) | Async primitives in tests | `anyio.from_thread.run_sync` if needed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncpg | psycopg3 async | psycopg3 async mode is newer, less battle-tested than asyncpg for high-throughput; asyncpg is the standard for FastAPI + PG |
| slowapi | fastapi-limiter (Redis) | fastapi-limiter requires Redis; slowapi uses in-memory counters — correct for single-user local tool |
| python-jose | authlib | authlib is heavier (OAuth2 full suite); python-jose is simpler for single-use HS256 |
| APScheduler | asyncio.create_task + sleep loop | APScheduler gives cron-like scheduling; sleep loop is fragile on drift |

**Installation (new packages only):**
```bash
pip install asyncpg>=0.31.0 python-jose[cryptography]>=3.5.0 passlib[bcrypt]>=1.7.4 bcrypt>=5.0.0 slowapi>=0.1.9 python-multipart>=0.0.22 apscheduler>=3.11.2 httpx>=0.28.1
```

**Version verification (confirmed against PyPI 2026-04-05):**
- asyncpg: 0.31.0 (latest)
- psycopg: 3.3.2 (already installed — latest is 3.3.3, but 3.3.2 is fine)
- python-jose: 3.5.0 (latest)
- passlib: 1.7.4 (latest — no newer release; project is in maintenance mode)
- bcrypt: 5.0.0 (latest)
- slowapi: 0.1.9 (latest)
- python-multipart: 0.0.22 (latest)
- APScheduler: 3.11.2 (latest)
- httpx: 0.28.1 (latest)

---

## Architecture Patterns

### Recommended Project Structure

```
pnpg/
├── api/
│   ├── __init__.py
│   ├── auth.py          # login endpoint, get_current_user dependency
│   ├── deps.py          # shared Depends() factories (db pool, current user)
│   ├── middleware.py     # rate limiter setup
│   ├── routes/
│   │   ├── connections.py   # GET /api/v1/connections
│   │   ├── alerts.py        # GET /api/v1/alerts, PATCH /api/v1/alerts/:id
│   │   ├── allowlist.py     # GET/POST/DELETE /api/v1/allowlist
│   │   ├── stats.py         # GET /api/v1/stats/summary, /timeseries
│   │   ├── status.py        # GET /api/v1/status, /health
│   │   └── ws.py            # WebSocket /api/v1/ws/live
│   └── models.py        # Pydantic request/response models
├── db/
│   ├── __init__.py
│   ├── pool.py          # create_pool(), get_pool() helpers
│   ├── schema.sql       # DDL — tables + indexes
│   ├── queries.py       # all SQL strings as named constants
│   └── migrations/      # versioned migration scripts (plain SQL)
├── storage/
│   ├── __init__.py
│   ├── writer.py        # storage_writer(event) — DB insert + NDJSON append
│   └── ndjson.py        # NdjsonWriter class with rotation logic
├── ws/
│   ├── __init__.py
│   └── manager.py       # WsManager class — client registry, batch timer, heartbeat
└── scheduler.py         # APScheduler setup — nightly purge, OBS-04 metrics
```

### Pattern 1: asyncpg Connection Pool Lifecycle

**What:** Create pool once at lifespan startup; close at shutdown. Pass pool via `app.state.db_pool`.
**When to use:** All DB operations — inserts from worker, SELECTs from route handlers.

```python
# pnpg/db/pool.py
import asyncpg

async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=10,
        command_timeout=5.0,         # query timeout
        server_settings={"application_name": "pnpg"},
    )

# In lifespan (main.py) — add after existing state setup:
# app.state.db_pool = await create_pool(config["db_dsn"])
# yield
# await app.state.db_pool.close()
```

**Key detail:** `asyncpg.Pool` is NOT thread-safe. Always use it from the asyncio event loop only — never from the executor thread. The pipeline worker is already async; route handlers are already async. This is safe as-is.

### Pattern 2: Storage Writer Hook in worker.py

**What:** After `detect_event()`, call `await storage_writer(event, alerts, app_state)`.
**When to use:** Every pipeline event (connection) AND every generated alert.

```python
# pnpg/storage/writer.py
async def storage_writer(
    event: dict,
    alerts: list[dict],
    db_pool: asyncpg.Pool,
    ndjson_writer: "NdjsonWriter",
    ws_manager: "WsManager",
) -> None:
    # 1. Insert connection into PostgreSQL
    await _insert_connection(db_pool, event)
    # 2. Append to NDJSON audit log
    await ndjson_writer.append("connections", event)
    # 3. Insert any alerts into PostgreSQL
    for alert in alerts:
        await _insert_alert(db_pool, alert)
        await ndjson_writer.append("alerts", alert)
    # 4. Push to live WebSocket clients
    await ws_manager.broadcast({"connections": [event], "alerts": alerts})
```

The worker.py stub comment `# Phase 5: storage_writer(event)` becomes:
```python
await storage_writer(event, alerts, app.state.db_pool, app.state.ndjson_writer, app.state.ws_manager)
```

**Problem:** `pipeline_worker` currently does not have access to `app.state`. Solution: pass `db_pool`, `ndjson_writer`, `ws_manager` as additional arguments to `pipeline_worker()` at task creation time in `main.py`, same pattern as existing `detector_state` argument.

### Pattern 3: JWT Auth Dependency

**What:** A `get_current_user` dependency that extracts and validates JWT from Authorization header.
**When to use:** Every protected route via `Depends(get_current_user)`.

```python
# pnpg/api/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    config: dict = Depends(get_config),
) -> str:
    try:
        payload = jwt.decode(
            credentials.credentials,
            config["jwt_secret"],
            algorithms=["HS256"],
        )
        return payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
```

### Pattern 4: WebSocket Manager with 500ms Batch Timer

**What:** A class that holds a registry of connected clients, buffers incoming events, and flushes every 500ms via an asyncio.Task.
**When to use:** Implements API-06, API-07, API-08, API-10.

```python
# pnpg/ws/manager.py
import asyncio
import time
from collections import defaultdict, deque
from fastapi import WebSocket

class WsManager:
    def __init__(self, batch_interval: float = 0.5, max_batch: int = 100):
        self._clients: dict[WebSocket, dict] = {}   # ws -> {filter: ..., queue: deque}
        self._interval = batch_interval
        self._max_batch = max_batch
        self._batch_task: asyncio.Task | None = None

    async def connect(self, ws: WebSocket, filter_: dict | None = None) -> None:
        await ws.accept()
        self._clients[ws] = {"filter": filter_ or {}, "queue": deque(maxlen=self._max_batch)}

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)

    async def broadcast(self, payload: dict) -> None:
        for ws, state in list(self._clients.items()):
            state["queue"].append(payload)

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            for ws, state in list(self._clients.items()):
                if not state["queue"]:
                    continue
                batch = list(state["queue"])
                state["queue"].clear()
                try:
                    await asyncio.wait_for(ws.send_json({"events": batch}), timeout=0.4)
                except Exception:
                    self.disconnect(ws)

    async def start(self) -> None:
        self._batch_task = asyncio.create_task(self._flush_loop(), name="ws-batch-flush")

    async def stop(self) -> None:
        if self._batch_task:
            self._batch_task.cancel()
```

**Heartbeat:** Separate asyncio.Task that calls `ws.send_json({"type": "heartbeat"})` every 10 seconds inside `_flush_loop` or as a sibling task.

### Pattern 5: Consistent API Envelope

**What:** All list responses return `{ "data": [...], "pagination": { "page": 1, "page_size": 50, "total": 1234 } }`. Single-object and action responses return `{ "data": {...} }`.
**When to use:** Every route handler — enforced via Pydantic generic response model.

```python
# pnpg/api/models.py
from pydantic import BaseModel, Generic, TypeVar
T = TypeVar("T")

class Pagination(BaseModel):
    page: int
    page_size: int
    total: int

class ListResponse(BaseModel, Generic[T]):
    data: list[T]
    pagination: Pagination

class SingleResponse(BaseModel, Generic[T]):
    data: T
```

### Pattern 6: NDJSON Writer with Rotation

**What:** Async file writer that appends JSON lines; checks file size before each write; rotates to `.1` suffix on exceed.
**When to use:** STORE-05, STORE-06, STORE-07.

```python
# pnpg/storage/ndjson.py
import asyncio, json, os
from pathlib import Path

class NdjsonWriter:
    def __init__(self, log_dir: str, max_bytes: int = 100 * 1024 * 1024):
        self._dir = Path(log_dir)
        self._max = max_bytes
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def append(self, name: str, record: dict) -> None:
        path = self._dir / f"{name}.ndjson"
        line = json.dumps(record, default=str) + "\n"
        async with self._lock:
            if path.exists() and path.stat().st_size + len(line) > self._max:
                path.replace(path.with_suffix(".ndjson.1"))
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)

    async def flush(self) -> None:
        pass  # Writes are immediate; flush is a no-op unless buffered I/O is added
```

**Note:** `asyncio.Lock` prevents concurrent writes from worker and any background tasks. File I/O remains synchronous (blocking) in this pattern — acceptable for ≤100MB files on local SSD. If throughput tests show file I/O is a bottleneck, wrap in `loop.run_in_executor`.

### Pattern 7: PostgreSQL Schema

```sql
-- pnpg/db/schema.sql

CREATE TABLE IF NOT EXISTS connections (
    event_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp    TIMESTAMPTZ NOT NULL,
    process_name TEXT NOT NULL,
    process_path TEXT,
    pid          INTEGER,
    src_ip       TEXT,
    src_port     INTEGER,
    dst_ip       TEXT,
    dst_port     INTEGER,
    dst_hostname TEXT,
    dst_country  TEXT,
    dst_asn      TEXT,
    dst_org      TEXT,
    protocol     TEXT,
    bytes_sent   BIGINT DEFAULT 0,
    bytes_recv   BIGINT DEFAULT 0,
    state        TEXT,
    is_blocklisted BOOLEAN DEFAULT FALSE,
    blocklist_source TEXT,
    severity     TEXT NOT NULL DEFAULT 'INFO',
    raw          JSONB              -- full event for future-proofing
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id         UUID PRIMARY KEY,
    timestamp        TIMESTAMPTZ NOT NULL,
    severity         TEXT NOT NULL,
    rule_id          TEXT NOT NULL,
    reason           TEXT,
    confidence       REAL,
    process_name     TEXT,
    pid              INTEGER,
    dst_ip           TEXT,
    dst_hostname     TEXT,
    recommended_action TEXT,
    suppressed       BOOLEAN DEFAULT FALSE,
    status           TEXT NOT NULL DEFAULT 'active'   -- active | suppressed | resolved
);

CREATE TABLE IF NOT EXISTS processes (
    process_name TEXT PRIMARY KEY,
    process_path TEXT,
    first_seen   TIMESTAMPTZ NOT NULL,
    last_seen    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS allowlist (
    rule_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_name TEXT,            -- NULL = global rule
    dst_ip       TEXT,
    dst_hostname TEXT,
    expires_at   TIMESTAMPTZ,     -- NULL = permanent
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason       TEXT
);

CREATE TABLE IF NOT EXISTS suppressions (
    suppression_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rule_id        TEXT,
    process_name   TEXT,          -- NULL = all processes
    scope          TEXT NOT NULL, -- 'single' | 'rule'
    reason         TEXT,
    alert_id       UUID REFERENCES alerts(alert_id) ON DELETE CASCADE
);

-- Indexes (STORE-10)
CREATE INDEX IF NOT EXISTS idx_connections_ts_proc
    ON connections (timestamp DESC, process_name);
CREATE INDEX IF NOT EXISTS idx_connections_dst_ip
    ON connections (dst_ip);
CREATE INDEX IF NOT EXISTS idx_alerts_ts_severity
    ON alerts (timestamp DESC, severity);
CREATE INDEX IF NOT EXISTS idx_alerts_status
    ON alerts (status);
```

### Pattern 8: First-Run Password Setup

**What:** On startup, if `data/auth.json` does not exist, block API with 503 and expose a `POST /api/v1/auth/setup` endpoint that accepts a password, stores its bcrypt hash, then disables the setup endpoint.
**When to use:** AUTH-04.

```python
# Simplified: check at lifespan startup
auth_file = Path("data/auth.json")
if not auth_file.exists():
    app.state.needs_setup = True
else:
    with open(auth_file) as f:
        app.state.password_hash = json.load(f)["hash"]
    app.state.needs_setup = False
```

### Anti-Patterns to Avoid

- **Calling asyncpg from a thread pool executor:** asyncpg connections are bound to the event loop that created them. Never pass a pool or connection to `run_in_executor`. Always await DB calls from async context.
- **One connection per request:** Always use the pool (`async with pool.acquire() as conn`). Opening a new connection per request kills performance.
- **Putting `event_id` generation in the DB only:** The pipeline event already carries `event_id` from Phase 1 (STORE-08 via `uuid` in worker output). INSERT should pass the existing UUID, not rely on `DEFAULT gen_random_uuid()`. Keep the default as a safety net.
- **Blocking the event loop with `open()` in the NDJSON writer:** The current pattern uses synchronous `open()` inside `asyncio.Lock`. This is acceptable for local SSD at current throughput. Do not use `aiofiles` unless benchmarks show file I/O exceeding 5ms p95.
- **Storing JWT secret in config.yaml (plain text, tracked in git):** JWT secret must come from an environment variable (`PNPG_JWT_SECRET`) or `data/secrets.json` (excluded from git via .gitignore). Never commit the secret.
- **Using FastAPI `on_event` (deprecated):** Already avoided — lifespan is in place. Extend the existing lifespan only.
- **Reloading `DetectorState.allowlist` from DB on every event:** Load on startup + on every POST/DELETE to allowlist table. Never query DB per pipeline event.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT encode/decode | Custom base64 + HMAC | python-jose | Handles expiry, claims, algorithm negotiation; edge cases in encoding are subtle |
| Password hashing | `hashlib.sha256(password)` | passlib[bcrypt] | bcrypt includes salt automatically; SHA-256 without salt is broken |
| DB connection pooling | `asyncio.Queue` of connections | asyncpg.create_pool | Pool handles health checks, reconnect, backpressure, max overflow |
| Rate limiting | Counter dict + asyncio.Lock | slowapi | Handles per-IP sliding window; integrates with FastAPI middleware; correct header injection |
| Cron scheduling | `asyncio.create_task` + `while True: sleep` | APScheduler AsyncIOScheduler | Handles DST, drift, missed jobs on resume |
| SQL query building | f-string interpolation | Named `$N` placeholders in asyncpg | f-string SQL = SQL injection vulnerability |

**Key insight:** The most dangerous hand-roll in this phase is SQL string interpolation. asyncpg uses `$1, $2, ...` positional parameters — always use these, never f-strings or `.format()` for values.

---

## Common Pitfalls

### Pitfall 1: asyncpg Pool Not Initialized Before First Request

**What goes wrong:** A request arrives before `lifespan` finishes creating the pool. `app.state.db_pool` is `None` → AttributeError.
**Why it happens:** FastAPI accepts requests as soon as `yield` is hit, but the pool may still be connecting.
**How to avoid:** Create the pool before `yield`. Add a `GET /api/v1/health` that catches `AttributeError` and returns `{"db": "initializing"}` during startup.
**Warning signs:** `AttributeError: 'State' object has no attribute 'db_pool'` in early requests.

### Pitfall 2: DetectorState.allowlist Out of Sync After API Write

**What goes wrong:** User POSTs a new allowlist rule via API. It's persisted to DB. But `detector_state.allowlist` (in-memory, used by `detect_event`) still has the old data. New connections from the now-allowed destination keep firing alerts.
**Why it happens:** The DB and the in-memory list are not automatically kept in sync.
**How to avoid:** After every successful `INSERT` into the `allowlist` table, immediately update `app.state.detector_state.allowlist` with the new rule dict. Similarly for DELETE. This is a single statement in the route handler.
**Warning signs:** Allowlist rules visible in `GET /api/v1/allowlist` but alerts still firing for those destinations.

### Pitfall 3: WebSocket Broadcast Loop Crashes on Disconnected Client

**What goes wrong:** `ws.send_json()` raises `WebSocketDisconnect` for a client that disconnected ungracefully. Unhandled exception kills the `_flush_loop` task. All remaining clients stop receiving updates.
**Why it happens:** `_flush_loop` iterates `self._clients.items()`. An exception inside the loop propagates out of the task.
**How to avoid:** Wrap each `ws.send_json()` in its own try/except. On any exception, call `self.disconnect(ws)` and continue the loop. Use `asyncio.wait_for` with timeout to drop slow clients (API-10).
**Warning signs:** WebSocket push stops after one client disconnects; no broadcast task exception in logs (if exception is swallowed by `asyncio.Task`).

### Pitfall 4: JWT Secret Rotation Breaks All Existing Tokens

**What goes wrong:** JWT secret changes (e.g., app restart reads new env var). All previously issued tokens are invalid. Single-user tool → user gets logged out.
**Why it happens:** HS256 validation requires the same secret used to sign.
**How to avoid:** Persist the JWT secret in `data/secrets.json` (created once, never rotated unless user explicitly requests). Do NOT read secret from an env var that can change between restarts. Alternatively, make 8h expiry acceptable (user just logs in again).
**Warning signs:** 401 errors on all requests immediately after restart.

### Pitfall 5: Nightly Purge Running While API is Under Load

**What goes wrong:** `DELETE FROM connections WHERE timestamp < NOW() - INTERVAL '30 days'` holds a table lock while thousands of live rows are being inserted by the pipeline worker. Inserts queue up; `drop_counter` increases; latency spikes.
**Why it happens:** `DELETE` on a large table is a heavy write operation.
**How to avoid:** Use APScheduler to run at 02:00 local time (low-traffic window). Add `LIMIT 10000` to the delete and loop until done (chunked delete). Add an index on `timestamp` (already required by STORE-10).
**Warning signs:** CPU spike at 02:00; log shows `db_write_latency_ms` increases during purge window.

### Pitfall 6: `passlib[bcrypt]` Deprecation Warning with bcrypt 4.x+

**What goes wrong:** `passlib` 1.7.4 was written before bcrypt 4.0 changed its internals. When used together, passlib emits a deprecation warning or raises an error about `__about__`.
**Why it happens:** `bcrypt` 4.0+ removed `bcrypt.__about__` which passlib 1.7.4 reads for version detection.
**How to avoid:** Pin `bcrypt>=4.0.0` and suppress the passlib warning with:
  ```python
  import warnings
  warnings.filterwarnings("ignore", ".*error reading bcrypt version.*")
  ```
  Or use `bcrypt` directly for hashing/verification without passlib if the warning is unacceptable.
  With bcrypt 5.0.0 (latest), the issue may be resolved — test on first install.
**Warning signs:** `AttributeError: module 'bcrypt' has no attribute '__about__'` in logs.

### Pitfall 7: NDJSON Writer asyncio.Lock is Not Re-Entrant

**What goes wrong:** If the worker calls `ndjson_writer.append()` from inside an `async with self._lock` block elsewhere, a deadlock occurs.
**Why it happens:** `asyncio.Lock` is not re-entrant (unlike `threading.RLock`).
**How to avoid:** Never call `append()` from within an existing lock context. Keep the lock strictly inside `NdjsonWriter.append()`.

### Pitfall 8: PostgreSQL Not Running — SYS-04 Handling

**What goes wrong:** `asyncpg.create_pool()` raises `ConnectionRefusedError` at lifespan startup if PostgreSQL is not running. Application fails to start.
**Why it happens:** Pool creation fails immediately if no server is reachable.
**How to avoid:** Wrap pool creation in try/except. On failure, set `app.state.db_pool = None` and `app.state.db_status = "unavailable"`. Route handlers that need DB check `app.state.db_pool` and return 503 if None. Retry pool creation in a background task every 30 seconds.
**Warning signs:** `ConnectionRefusedError` during startup; app exits before accepting any requests.

---

## Code Examples

### asyncpg INSERT with positional parameters

```python
# pnpg/db/queries.py — STORE-01
INSERT_CONNECTION = """
INSERT INTO connections (
    event_id, timestamp, process_name, process_path, pid,
    src_ip, src_port, dst_ip, dst_port, dst_hostname,
    dst_country, dst_asn, dst_org, protocol,
    bytes_sent, bytes_recv, state, is_blocklisted,
    blocklist_source, severity, raw
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
)
ON CONFLICT (event_id) DO NOTHING
"""

# Usage in writer.py:
async def _insert_connection(pool: asyncpg.Pool, event: dict) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            INSERT_CONNECTION,
            event["event_id"], event["timestamp"], event["process_name"],
            event.get("process_path"), event.get("pid"),
            event.get("src_ip"), event.get("src_port"),
            event.get("dst_ip"), event.get("dst_port"),
            event.get("dst_hostname"), event.get("dst_country"),
            event.get("dst_asn"), event.get("dst_org"),
            event.get("protocol"), event.get("bytes_sent", 0),
            event.get("bytes_recv", 0), event.get("state"),
            event.get("threat_intel", {}).get("is_blocklisted", False),
            event.get("threat_intel", {}).get("source"),
            event.get("severity", "INFO"),
            json.dumps(event),  # raw JSONB
        )
```

### JWT login endpoint

```python
# pnpg/api/auth.py
from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    password: str

@router.post("/auth/login")
async def login(body: LoginRequest, request: Request) -> dict:
    config = request.app.state.config
    stored_hash = request.app.state.password_hash
    if not pwd_context.verify(body.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    now = datetime.now(timezone.utc)
    access_token = jwt.encode(
        {"sub": "pnpg-user", "iat": now, "exp": now + timedelta(hours=8)},
        config["jwt_secret"],
        algorithm="HS256",
    )
    refresh_token = jwt.encode(
        {"sub": "pnpg-user", "iat": now, "exp": now + timedelta(days=30), "type": "refresh"},
        config["jwt_secret"],
        algorithm="HS256",
    )
    return {"data": {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}}
```

### WebSocket endpoint with JWT query param auth

```python
# pnpg/api/routes/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

router = APIRouter()

@router.websocket("/ws/live")
async def ws_live(
    websocket: WebSocket,
    token: str = Query(...),
    request_state=None,
) -> None:
    # Validate token BEFORE accept to avoid orphaned connections
    try:
        jwt.decode(token, websocket.app.state.config["jwt_secret"], algorithms=["HS256"])
    except JWTError:
        await websocket.close(code=4001)
        return

    manager = websocket.app.state.ws_manager
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "filter":
                manager.set_filter(websocket, data.get("data", {}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

### Pagination query pattern

```python
# GET /api/v1/connections — API-01, API-13
SELECT_CONNECTIONS = """
SELECT * FROM connections
WHERE ($1::text IS NULL OR process_name = $1)
  AND ($2::text IS NULL OR dst_ip = $2)
  AND ($3::timestamptz IS NULL OR timestamp >= $3)
  AND ($4::timestamptz IS NULL OR timestamp <= $4)
ORDER BY timestamp DESC
LIMIT $5 OFFSET $6
"""
COUNT_CONNECTIONS = """
SELECT COUNT(*) FROM connections
WHERE ($1::text IS NULL OR process_name = $1)
  AND ($2::text IS NULL OR dst_ip = $2)
  AND ($3::timestamptz IS NULL OR timestamp >= $3)
  AND ($4::timestamptz IS NULL OR timestamp <= $4)
"""
```

### Rate limiting with slowapi

```python
# pnpg/api/middleware.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI

limiter = Limiter(key_func=get_remote_address)

def setup_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Usage on a route:
# @router.get("/connections")
# @limiter.limit("100/minute")
# async def get_connections(request: Request, ...): ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `on_event("startup")` decorator | `lifespan` async context manager | FastAPI 0.93 (2023) | `on_event` still works but deprecated; lifespan is already in place |
| psycopg2 + sync threading | asyncpg + asyncio | 2020-2022 | asyncpg is ~3x faster for async workloads; no thread overhead |
| WinPcap | Npcap | 2013 (WinPcap EOL) | Already accounted for in Phase 1 |
| HS512 JWT | HS256 JWT | N/A | HS256 is the CLAUDE.md constraint; both are secure for local single-user |

**Deprecated/outdated:**
- `@app.on_event`: Do not add any new `on_event` decorators. Extend the existing lifespan only.
- `databases` library (async DB wrapper): Was popular 2019-2021; asyncpg directly is now preferred for PostgreSQL-only projects.
- `aiofiles`: Not needed for this throughput level; synchronous file I/O inside asyncio.Lock is acceptable.

---

## Runtime State Inventory

> Step 2.5: No rename/refactor work in this phase. Included for completeness.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | No persistent DB yet — Phase 5 creates it | Phase 5 creates schema from DDL |
| Live service config | PostgreSQL must be running before startup | Install and start PostgreSQL service |
| OS-registered state | None | None |
| Secrets/env vars | `PNPG_JWT_SECRET` — new env var needed | Add to `data/secrets.json` or env; document in config.yaml |
| Build artifacts | None | None |

**New config keys to add to `DEFAULT_CONFIG`:**
```python
"db_dsn": "postgresql://pnpg:pnpg@localhost:5432/pnpg",
"db_pool_min": 2,
"db_pool_max": 10,
"jwt_secret": "",             # Empty = read from data/secrets.json or PNPG_JWT_SECRET env
"jwt_expiry_hours": 8,
"ws_batch_interval_ms": 500,
"ws_max_batch_size": 100,
"ws_heartbeat_interval_s": 10,
"ndjson_max_size_mb": 100,
"retention_connections_days": 30,
"retention_alerts_days": 90,
"purge_schedule_hour": 2,     # 02:00 local time
"api_rate_limit": "100/minute",
"auth_file": "data/auth.json",
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | STORE-01..11, all API endpoints | Partial | psql 18.1 in PATH, but port 5432 not responding | Must start PostgreSQL service before Phase 5 tests; SYS-04 handles runtime unavailability |
| asyncpg | DB async driver | Not installed | — | Must install via pip |
| python-jose | JWT auth | Not installed | — | No viable fallback — must install |
| passlib | Password hashing | Not installed | — | Could use bcrypt directly; passlib preferred for API stability |
| bcrypt | bcrypt backend for passlib | Not installed | — | Must install |
| slowapi | Rate limiting | Not installed | — | Could skip and implement in-process counter; slowapi preferred |
| python-multipart | Form parsing | Not installed | — | Must install if using OAuth2PasswordRequestForm |
| APScheduler | Nightly purge, OBS-04 | Not installed | — | Could use asyncio task + sleep loop as fallback |
| httpx | Async test client | Not installed | — | `pytest-anyio` + `httpx` is the standard for FastAPI testing |
| psycopg3 | Already installed | 3.3.2 | Usable for DDL migration scripts | — |
| FastAPI | Already installed | 0.135.2 | Current stable | — |
| uvicorn | Already installed | 0.42.0 | Current stable | — |
| pytest-asyncio | Already installed | 1.3.0 | Current stable | — |

**Missing dependencies with no fallback:**
- `asyncpg` — blocking for all DB writes
- `python-jose[cryptography]` — blocking for JWT auth (AUTH-01..04)
- `bcrypt` — blocking for password hashing (AUTH-04)

**Missing dependencies with fallback:**
- `passlib` — can use `bcrypt` directly if passlib/bcrypt compatibility issues arise
- `slowapi` — can implement simple counter; use slowapi for correctness
- `APScheduler` — can use `asyncio.create_task` + sleep loop as degraded fallback
- `python-multipart` — only needed if using form body for login; JSON body avoids this

**PostgreSQL service:** `psql` v18.1 is installed but the PostgreSQL server process is not running on port 5432. Wave 0 (setup tasks) must include starting the PostgreSQL service and creating the `pnpg` database and user before any schema migration can run.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` (exists; `asyncio_mode = auto`) |
| Quick run command | `pytest tests/test_pipeline/ tests/test_api/ -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STORE-01 | INSERT connection to `connections` table | unit (mock pool) | `pytest tests/test_storage/test_writer.py -x` | Wave 0 |
| STORE-02 | INSERT alert to `alerts` table | unit (mock pool) | same file | Wave 0 |
| STORE-05/06 | NDJSON append writes correct JSON line | unit | `pytest tests/test_storage/test_ndjson.py -x` | Wave 0 |
| STORE-07 | NDJSON rotates at max size | unit | same file | Wave 0 |
| STORE-10 | Indexes present in schema | integration | manual SQL `\d` check or schema diff | N/A |
| STORE-11 | Purge deletes rows older than retention | unit (mock conn) | `pytest tests/test_storage/test_purge.py -x` | Wave 0 |
| AUTH-01 | POST /auth/login returns JWT with valid password | integration | `pytest tests/test_api/test_auth.py::test_login_success -x` | Wave 0 |
| AUTH-01 | POST /auth/login returns 401 with wrong password | integration | `pytest tests/test_api/test_auth.py::test_login_fail -x` | Wave 0 |
| AUTH-02 | Protected route returns 401 without token | integration | `pytest tests/test_api/test_auth.py::test_protected_no_token -x` | Wave 0 |
| AUTH-03 | WebSocket closes with code 4001 on bad token | integration | `pytest tests/test_api/test_ws.py::test_ws_bad_token -x` | Wave 0 |
| API-01 | GET /connections returns paginated envelope | integration | `pytest tests/test_api/test_connections.py -x` | Wave 0 |
| API-06 | WebSocket pushes batch within 600ms | integration | `pytest tests/test_api/test_ws.py::test_ws_batch_timing -x` | Wave 0 |
| API-08 | Broadcast loop survives client disconnect | unit | `pytest tests/test_ws/test_manager.py::test_broadcast_survives_disconnect -x` | Wave 0 |
| API-10 | Slow client dropped after timeout | unit | `pytest tests/test_ws/test_manager.py::test_slow_client_dropped -x` | Wave 0 |
| ALLOW-05 | POST /allowlist persists to DB and syncs DetectorState | integration | `pytest tests/test_api/test_allowlist.py -x` | Wave 0 |
| SUPP-05 | PATCH /alerts/:id suppress updates status | integration | `pytest tests/test_api/test_alerts.py::test_suppress_alert -x` | Wave 0 |
| SYS-04 | GET /health returns 503 when pool is None | unit | `pytest tests/test_api/test_health.py::test_db_unavailable -x` | Wave 0 |
| TEST-02 | Load generator produces N events/sec | smoke | `python tools/load_generator.py --rate 100 --duration 5` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_storage/ tests/test_ws/ tests/test_api/ -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_storage/` directory + `test_writer.py`, `test_ndjson.py`, `test_purge.py`
- [ ] `tests/test_ws/test_manager.py` — WsManager unit tests
- [ ] `tests/test_api/` directory + `test_auth.py`, `test_connections.py`, `test_alerts.py`, `test_allowlist.py`, `test_ws.py`, `test_health.py`
- [ ] `tools/load_generator.py` — TEST-02 synthetic traffic script
- [ ] PostgreSQL test database: `createdb pnpg_test` with schema applied
- [ ] Fixture: `conftest.py` additions — `db_pool` fixture (async, uses test DB or mock pool), `ws_manager` fixture, `auth_headers` fixture (valid JWT for protected route tests)
- [ ] Install new packages: `pip install asyncpg>=0.31.0 python-jose[cryptography]>=3.5.0 passlib[bcrypt]>=1.7.4 bcrypt>=5.0.0 slowapi>=0.1.9 python-multipart>=0.0.22 apscheduler>=3.11.2 httpx>=0.28.1`

---

## Open Questions

1. **PostgreSQL test database strategy**
   - What we know: PostgreSQL v18.1 is installed but not running. Tests that hit real DB need a test database.
   - What's unclear: Should tests use a real local PostgreSQL instance, or mock `asyncpg.Pool` entirely with `unittest.mock`?
   - Recommendation: Mock the pool for unit tests (no external dependency); add one integration test suite that requires a running DB and is skipped (`pytest.mark.skipif`) if `PNPG_TEST_DB_DSN` env var is absent. This makes CI-free development possible.

2. **JWT secret bootstrapping**
   - What we know: Secret must not be in git. Must survive restarts.
   - What's unclear: Whether the user will set `PNPG_JWT_SECRET` env var or prefer an auto-generated file.
   - Recommendation: On first startup, if neither env var nor `data/secrets.json` exists, auto-generate a random 32-byte hex secret and write to `data/secrets.json` (add to .gitignore). Log a one-time warning that the secret was generated.

3. **processes table UPSERT pattern**
   - What we know: Every connection event should update `processes.last_seen`.
   - What's unclear: This means every insert to `connections` also triggers an UPSERT to `processes`. At 10,000 events/sec (Phase 7 target), this is 10,000 UPSERTs/sec to a small table.
   - Recommendation: Batch process UPSERTs — maintain an in-memory `set` of (process_name, path) pairs seen in the last 5 seconds; flush to DB as a batch INSERT ON CONFLICT every 5 seconds via APScheduler. Do not UPSERT per-event.

4. **SUPP-04 requirement scope**
   - What we know: SUPP-04 (suppression log viewable in dashboard with undo) is mapped to Phase 6 (frontend), not Phase 5.
   - What's unclear: Phase 5 needs to provide the API for it — specifically `GET /api/v1/suppressions` is not listed in API-01..13 but is implied by SUPP-04.
   - Recommendation: Add `GET /api/v1/suppressions` to Phase 5 API work even though the frontend consuming it is Phase 6. Prevents Phase 6 from being blocked by missing API.

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 5 |
|-----------|-------------------|
| PostgreSQL 15+ as primary store; no SQLite | Use asyncpg pool; schema must target PG 15+ SQL features |
| asyncpg or psycopg3 for async writes | Use asyncpg for all pipeline and API DB writes |
| JWT HS256, 8h expiry, single-user local auth | python-jose[cryptography]; HS256 only; no refresh token rotation complexity |
| NDJSON flat files as audit log; 100MB rotation | NdjsonWriter with size check on every append |
| No external network calls from tool itself | All enrichment local; JWT verification is local; no external auth service |
| Python 3.11+, FastAPI, asyncio pipeline | Already met; all new code must be async |
| No framework substitutions | FastAPI only; no aiohttp, Flask, etc. |
| Files max 800 lines; prefer 200-400 lines | Split route handlers into separate files per domain (connections.py, alerts.py, etc.) |
| No hardcoded values; use constants or config | All thresholds in `DEFAULT_CONFIG`; SQL strings in `queries.py` constants |
| Immutable patterns: always return new objects | Pydantic models enforce this for API responses; DB rows → new dict, not mutation |
| Validate all user input at system boundaries | Use Pydantic models for all request bodies; asyncpg parameterized queries |
| No magic numbers in code | All durations, sizes, limits come from config dict |

---

## Sources

### Primary (HIGH confidence)

- PyPI registry (verified 2026-04-05): asyncpg 0.31.0, psycopg 3.3.2, python-jose 3.5.0, passlib 1.7.4, bcrypt 5.0.0, slowapi 0.1.9, python-multipart 0.0.22, APScheduler 3.11.2, httpx 0.28.1
- Existing codebase inspection: `pnpg/main.py`, `pnpg/pipeline/worker.py`, `pnpg/config.py`, `pnpg/pipeline/detector.py` — all read directly
- `pytest.ini` — confirmed `asyncio_mode = auto`; test infrastructure in place

### Secondary (MEDIUM confidence)

- asyncpg documentation patterns (pool lifecycle, `$N` placeholders) — consistent with training data and widely reproduced in FastAPI ecosystem tutorials
- FastAPI lifespan pattern — confirmed present in codebase already; extending it follows documented pattern
- slowapi integration pattern — matches official slowapi README (verified against PyPI page description)

### Tertiary (LOW confidence)

- passlib + bcrypt 4.x/5.x compatibility warning — based on training data knowledge of the breaking change; should be validated empirically on first install
- APScheduler `AsyncIOScheduler` integration with FastAPI lifespan — training data; should be validated against APScheduler 3.11.2 docs

---

## Metadata

**Confidence breakdown:**
- Standard stack versions: HIGH — verified against PyPI registry live
- Architecture patterns: HIGH — derived from existing codebase + established FastAPI/asyncpg conventions
- Integration hooks (worker.py stubs): HIGH — read directly from source
- Pitfalls: MEDIUM-HIGH — most from known asyncpg/FastAPI/passlib behaviors; bcrypt compatibility is MEDIUM
- Test map: HIGH — derived from requirement list + existing test infrastructure

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (30 days — stable libraries; APScheduler/asyncpg versions unlikely to break)
