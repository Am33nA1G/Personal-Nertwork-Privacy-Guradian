<!-- GSD:project-start source:PROJECT.md -->
## Project

**Personal Network Privacy Guardian (PNPG)**

A real-time network monitoring system that captures outgoing traffic from a user's device, maps connections to the applications generating them, resolves IP addresses to domain names, and flags suspicious activity through rule-based anomaly detection. Everything is displayed in a clean web dashboard built for users who have no deep networking expertise.

**Core Value:** Users can see exactly which apps are talking to the internet and get alerted when something looks suspicious — without needing to understand Wireshark.

### Constraints

- **Privileges**: Admin/root required — Scapy needs raw socket access
- **Tech Stack**: Python 3.10+, FastAPI, Scapy, psutil, socket, uvicorn; HTML/CSS/JS + Chart.js frontend — no framework changes
- **Local Only**: No external network calls from the tool itself; all resolution is local DNS
- **Storage**: JSON flat files for v1 — no database dependency
- **Performance**: Detection rules must be lightweight enough to not block the sniff loop
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
| Vanilla HTML/CSS/JS | — | UI shell | Correct for this scope. No framework needed; adding React/Vue would add build tooling complexity with zero benefit for a single-page local tool. |
| Chart.js | 4.x | Data visualization (connections/sec, per-app usage) | The right choice. Lightweight, zero-dependency CDN delivery, well-documented canvas-based charts. Version 4.x (not 3.x) — breaking changes between 3 and 4 include dataset configuration structure. Use CDN: `https://cdn.jsdelivr.net/npm/chart.js@4`. |
| Bootstrap | 5.3.x (optional) | UI component styling | Listed as optional in PRD. Use it — the time savings on table/alert styling are real and the CDN delivery keeps zero build steps. Bootstrap 5 (not 4) — no jQuery dependency. |
| Native WebSocket API | Browser built-in | Real-time connection to `/ws/live` | Correct. The browser `WebSocket` constructor is all that is needed; no `socket.io` or similar library required. |
### Data Storage Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python in-memory list/dict | stdlib | Live connection buffer | Correct for v1. A `collections.deque(maxlen=N)` is better than a plain list for bounded circular logging — prevents unbounded memory growth under sustained traffic. |
| JSON flat files | stdlib `json` module | Persistent log of connections and alerts | Correct for v1. Use append-mode logging with rotation logic or a size cap — naively growing a single JSON file will become unreadable quickly. Recommend writing newline-delimited JSON (NDJSON) rather than a single array, so log readers don't need to parse the entire file. |
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
