<!-- GSD:project-start source:PROJECT.md -->
## Project

**Personal Network Privacy Guardian (PNPG)**

A real-time network monitoring system that captures outgoing traffic from a user's device, maps connections to the applications generating them, resolves IP addresses to domain names, and flags suspicious activity through rule-based anomaly detection. Everything is displayed in a clean web dashboard built for users who have no deep networking expertise.

**Core Value:** Users can see exactly which apps are talking to the internet and get alerted when something looks suspicious — without needing to understand Wireshark.

### Constraints

- **Privileges**: Admin/root required — Scapy/libpcap needs raw socket access; Linux eBPF requires CAP_BPF + CAP_PERFMON
- **Tech Stack**: Python 3.11+, FastAPI, Scapy, psutil, socket, uvicorn; React 18 / Next.js 14 + Recharts frontend — no framework substitutions
- **Local Only**: No external network calls from the tool itself; all enrichment uses local databases (GeoIP, threat intel blocklist)
- **Storage**: PostgreSQL 15+ as primary store; NDJSON flat files as audit log — no SQLite
- **Stream layer**: asyncio bounded queue (current) → Redis Streams (MVP) → Kafka (V1+)
- **Auth**: JWT (HS256, 8h expiry) on all API endpoints; single-user local auth only
- **Performance**: ≥10,000 events/sec sustained with <2% drop; p95 end-to-end latency <100ms
- **Deployment**: Docker Compose for MVP; Kubernetes for V1 production
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Capture Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ (use 3.11 or 3.12) | Runtime | 3.11 delivers ~25% speed improvement over 3.10 via specializing adaptive interpreter; 3.12 adds further optimizations. 3.10 is the floor but 3.11+ is preferred for the sniff-loop performance. |
| Scapy | 2.5.x (latest stable) | Packet capture and packet parsing | De facto standard for Python packet manipulation. Built-in BPF filter support. No viable pure-Python alternative for raw socket capture at this abstraction level. |
| Npcap | 1.79+ (latest) | Windows packet capture driver (required by Scapy on Windows) | WinPcap is **dead** (last released 2013, EOL). Npcap is the maintained successor. Scapy on Windows will not function without it. Install with "WinPcap API-compatible mode" enabled. |
### Process Mapping Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| psutil | 5.9.x or 6.x | Map network connections to PIDs and process names | The only mature cross-platform library for this. `net_connections()` is the exact API needed to correlate local IP+port pairs from Scapy captures to OS-level process information. |
### DNS Resolution Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| socket (stdlib) | Python stdlib | Reverse DNS lookup | `socket.gethostbyaddr(ip)` is synchronous and blocks. This is acceptable only if DNS calls are dispatched to a thread pool (see Architecture notes below). No third-party library needed for v1. |
### Backend API Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.110.x–0.115.x | REST API + WebSocket server | Correct choice. Async-native, built-in WebSocket via Starlette, auto OpenAPI docs, minimal boilerplate. The `WebSocket` class in FastAPI handles the `/ws/live` endpoint cleanly. |
| uvicorn | 0.29.x–0.32.x | ASGI server | The standard pairing for FastAPI. Use `uvicorn[standard]` to pull in `websockets` and `httptools` for better performance. |
| websockets | 12.x (pulled by uvicorn[standard]) | WebSocket protocol implementation | Pulled in transitively; do not pin separately. |
### Frontend Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| ~~Vanilla HTML/CSS/JS~~ **React 18** | 18.x | UI framework | **CHANGED (PRD upgrade 2026-04-04):** Allowlist Manager + alert suppress/resolve + GeoIP columns require component architecture; Vanilla JS is no longer adequate |
| ~~Chart.js~~ **Recharts** | 2.x | Data visualization | **CHANGED:** Recharts is React-native; simpler integration than Chart.js when already in a React app |
| Bootstrap | 5.3.x | UI component styling | Use via npm (not CDN) in the Next.js project. Bootstrap 5 — no jQuery dependency. |
| Next.js | 14.x | React framework + dev server | File-based routing; `next dev` server; serves the SPA locally |
| Native WebSocket API | Browser built-in | Real-time connection to `/api/v1/ws/live` | No change — browser WebSocket constructor, exponential backoff reconnect |
### Data Storage Layer
> **PRD Upgrade (2026-04-04):** Storage upgraded from JSON flat files to PostgreSQL 15+ as primary. NDJSON files retained as audit/fallback log. No SQLite.

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 15+ | Primary event and alert storage | **CHANGED:** Required by PRD upgrade — supports indexed queries, 30-day retention with nightly purge, allowlist/suppression tables. Use `asyncpg` or `psycopg3` for async writes from FastAPI. |
| Python in-memory deque | stdlib | Live connection buffer | `collections.deque(maxlen=N)` for bounded circular buffer — still needed as write-ahead buffer before DB flush |
| NDJSON flat files | stdlib `json` module | Append-only audit log; graceful-shutdown flush | Retained as lightweight audit log and offline fallback. Append-mode with rotation (100MB cap). |
| ClickHouse | optional | High-volume `connections` analytics | Use only when connection volume exceeds 1M events/day. Not needed for MVP. |
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
| Charts | ~~Chart.js~~ **Recharts** | D3.js / Chart.js | **CHANGED (PRD upgrade):** Recharts integrates natively in React; Chart.js requires wrapper boilerplate in a React app |
| Frontend | ~~Vanilla JS~~ **React 18 / Next.js 14** | Vanilla JS | **CHANGED (PRD upgrade):** Allowlist Manager + alert actions + GeoIP columns require component state management; Vanilla JS becomes unmanageable at this scope |
| Storage | ~~JSON files~~ **PostgreSQL 15+** | SQLite | **CHANGED (PRD upgrade):** PRD now requires 30-day retention, indexed queries, allowlist table, suppressions table — PostgreSQL is the correct choice |
## Windows-Specific Considerations
### 1. Npcap is a hard prerequisite — not optional
- `from scapy.all import sniff` will succeed (import works)
- Calling `sniff()` will raise `OSError: [Errno 22] Invalid argument` or fail silently with no packets captured
### 2. Administrator elevation is mandatory — handle gracefully
### 3. Interface selection on Windows differs from Linux
### 4. BPF filter behavior differs between Windows and Linux
### 5. psutil elevation dependency on Windows
## Installation
# Core backend
# No additional packages needed for v1
## PRD Validation — What to Keep, What to Change
| PRD Decision | Verdict | Notes |
|--------------|---------|-------|
| Scapy for packet capture | KEEP | Correct. No better alternative for this use case. libpcap fallback for Linux kernel <5.8. |
| psutil for process mapping | KEEP | Correct. Wrap in try/except for AccessDenied on Windows. |
| socket for DNS | KEEP with caveat | Must be run off the main thread. Blocking DNS calls stall the sniffer — non-negotiable. |
| FastAPI | KEEP | Correct. Use `lifespan` not `on_event` for startup. All endpoints under /api/v1/ with JWT auth. |
| uvicorn | KEEP | Use `uvicorn[standard]` not bare `uvicorn` to include websockets dependency. |
| ~~HTML/JS frontend~~ React 18 / Next.js 14 | **CHANGE** | PRD upgrade: Allowlist Manager + alert actions require component architecture. Use Recharts, not Chart.js. |
| ~~Chart.js~~ Recharts 2.x | **CHANGE** | React-native charting; use Recharts inside the Next.js app. |
| Bootstrap | KEEP | Use via npm in Next.js project. Bootstrap 5 — no jQuery. |
| ~~JSON flat file storage~~ PostgreSQL 15+ | **CHANGE** | PRD upgrade: PostgreSQL is primary; NDJSON retained as audit log. asyncpg or psycopg3 for async writes. |
| No SQLite v1 | KEEP | Still correct — use PostgreSQL, not SQLite. |
| requirements.txt without versions | CHANGE | Pin minimum versions (`>=`) to avoid pulling in breaking changes. |
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
## Sources
- Training data (knowledge cutoff August 2025): FastAPI docs, Scapy official docs, psutil changelog, uvicorn releases
- Note: External sources (PyPI, official documentation sites) were unavailable during this research session due to tool permission restrictions. Version numbers cited as MEDIUM confidence should be validated against PyPI before pinning in requirements.txt.
- Validate Scapy current version: https://pypi.org/project/scapy/
- Validate FastAPI current version: https://pypi.org/project/fastapi/
- Validate uvicorn current version: https://pypi.org/project/uvicorn/
- Validate psutil current version: https://pypi.org/project/psutil/
- Npcap (Windows driver): https://npcap.com
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
