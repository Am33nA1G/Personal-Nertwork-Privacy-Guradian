# Roadmap: Personal Network Privacy Guardian (PNPG)

## Overview

Six phases that build the PNPG pipeline from the ground up in dependency order: first establish the threading architecture that everything else relies on (Phase 1), then add process attribution and DNS resolution as independent data-enrichment layers (Phases 2 and 3), then stack the detection engine on top of those enriched events (Phase 4), then wire up the storage and API layer that exposes the pipeline (Phase 5), and finally build the dashboard that makes it useful to a non-expert user (Phase 6). No phase is optional; each is a prerequisite for the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Capture Foundation** - Establish the Scapy threading architecture, Windows prerequisites, and async queue bridge that all subsequent phases depend on
- [ ] **Phase 2: Process Attribution** - Enrich captured packets with originating process name and PID using a psutil polling cache
- [ ] **Phase 3: DNS Resolution** - Resolve destination IPs to domain names via a thread-pool-backed reverse DNS cache
- [ ] **Phase 4: Detection Engine** - Apply four rule-based anomaly detection rules to enriched connection events and emit alerts
- [ ] **Phase 5: Data Store and Backend API** - Persist events to bounded in-memory store and NDJSON logs; expose via FastAPI REST and WebSocket
- [ ] **Phase 6: Frontend Dashboard** - Live web dashboard that consumes the WebSocket feed and renders connections, alerts, and charts

## Phase Details

### Phase 1: Capture Foundation
**Goal**: The system captures live outgoing packets on Windows, validates all prerequisites, bridges the blocking Scapy thread to FastAPI's async world via a bounded queue, and fails loudly if prerequisites are missing
**Depends on**: Nothing (first phase)
**Requirements**: CAP-01, CAP-02, CAP-03, CAP-04, CAP-05, CAP-06, CAP-07, CAP-08, CAP-09, CAP-10, CONFIG-01, CONFIG-02, CONFIG-03, SYS-01, PIPE-01, PIPE-02, PIPE-03, TEST-01
**Success Criteria** (what must be TRUE):
  1. Running the application without Npcap installed prints a clear error message and exits before any sniffing starts
  2. Running without administrator privileges prints a clear error message and exits before any sniffing starts
  3. Packets are visible in the async queue within 5 seconds of startup on the correct network interface (auto-selected or overridden via config.yaml or CLI flag)
  4. When the queue hits maxsize=500, the oldest packet is dropped and an INFO log entry is emitted — the sniffer does not block or crash
  5. If the sniffer thread dies, it restarts automatically with exponential backoff and logs each restart attempt
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Windows prerequisites (Npcap check, admin check) and config.yaml loader with defaults
- [ ] 01-02-PLAN.md — Scapy sniffer daemon thread, interface auto-selection, asyncio queue bridge with drop-head
- [ ] 01-03-PLAN.md — Sniffer supervisor with exponential backoff restart, async pipeline worker, FastAPI lifespan

### Phase 2: Process Attribution
**Goal**: Every packet event in the queue is annotated with the originating process name and PID using a proactive psutil polling cache; unattributable connections degrade gracefully to "unknown process"
**Depends on**: Phase 1
**Requirements**: PROC-01, PROC-02, PROC-03, PROC-04, PROC-05, PROC-06
**Success Criteria** (what must be TRUE):
  1. Each connection event carries a process name and PID field visible in the pipeline output (e.g., printed to console during testing)
  2. Connections from system processes (where psutil raises AccessDenied) show "unknown process" and PID -1 without crashing
  3. Short-lived connections that disappear before the cache updates show "unknown process" rather than hanging or erroring
  4. psutil.net_connections() is called on a 200ms background schedule — never once per packet — confirmed by log timestamps
  5. Cache entries expire after the configured TTL (default 2 seconds) so stale PIDs do not persist indefinitely
**Plans**: TBD

Plans:
- [ ] 02-01: psutil background poller (200ms interval) with TTL-expiring connection cache
- [ ] 02-02: Packet-to-process correlation using (src_ip, src_port) lookup; graceful fallback to "unknown process"

### Phase 3: DNS Resolution
**Goal**: Destination IP addresses in each connection event are resolved to human-readable domain names using a thread-pool-backed reverse DNS cache with timeout protection; unresolvable IPs fall back to raw IP display
**Depends on**: Phase 2
**Requirements**: DNS-01, DNS-02, DNS-03, DNS-04, DNS-05, DNS-06
**Success Criteria** (what must be TRUE):
  1. Connection events for well-known destinations (e.g., google.com) show the domain name rather than raw IP in pipeline output
  2. An IP with no PTR record resolves to the raw IP string within 2 seconds — the pipeline does not stall waiting for DNS
  3. DNS lookups never run on the asyncio event loop — verified by confirming the event loop remains unblocked during a burst of new IPs
  4. The same IP is not looked up twice within its TTL window — confirmed by log showing cache hit for repeated destinations
**Plans**: TBD

Plans:
- [ ] 03-01: Thread pool DNS resolver with 2-second timeout, TTL-keyed result cache (including negative caching), and LRU eviction at 1000-entry limit (DNS-06)
- [ ] 03-02: Integration of DNS resolver into the pipeline worker; raw IP fallback for unresolvable addresses

### Phase 4: Detection Engine
**Goal**: Fully enriched connection events are evaluated against anomaly detection rules (DET-01 through DET-06: unknown domain, high rate, unusual port + unknown process, unknown process); violations emit timestamped alerts with severity; alert flooding is rate-limited to 1 alert per rule per second
**Depends on**: Phase 3
**Requirements**: DET-01, DET-02, DET-03, DET-04, DET-05, DET-06
**Success Criteria** (what must be TRUE):
  1. A connection with no resolvable domain emits a WARNING alert visible in the alert stream
  2. Sending more than 50 connections per second from a single process triggers a DET-02 ALERT within that second
  3. A connection on port 9999 from an unknown process emits an alert; a connection on port 9999 from a known process at normal frequency does not (false-positive gate confirmed)
  4. A connection from "unknown process" emits a DET-04 ALERT
  5. When a rule fires continuously, no more than 1 alert per rule per second appears in the output (rate limiter confirmed by log count)
  6. All thresholds (rate, port allowlist) are read from config.yaml named constants — no magic numbers in detection code
**Plans**: TBD

Plans:
- [ ] 04-01: Detection rule implementations (DET-01 through DET-04) using named constants from config
- [ ] 04-02: Per-rule rate limiter (max 1 alert/rule/second) and alert object construction

### Phase 5: Data Store and Backend API
**Goal**: Connection and alert events are held in bounded in-memory deques and written to NDJSON log files with rotation; FastAPI exposes four REST endpoints and a WebSocket that batches updates at 500ms intervals; graceful shutdown flushes memory to disk
**Depends on**: Phase 4
**Requirements**: STORE-01, STORE-02, STORE-03, STORE-04, STORE-05, STORE-06, STORE-07, API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08, API-09, API-10, SYS-02, PERF-01, PERF-02, TEST-02, MET-01
**Success Criteria** (what must be TRUE):
  1. GET /connections returns JSON with the last N connections including app, domain, IP, port, protocol, and timestamp fields
  2. GET /alerts returns active alerts with severity, rule name, and connection reference
  3. GET /stats returns connections-per-app counts, estimated total bytes, and connections-per-second
  4. GET /status returns capture state (running/stopped), interface name, and uptime
  5. A browser WebSocket client connected to /ws/live receives batched pushes approximately every 500ms (not one message per packet)
  6. Disconnecting a WebSocket client does not crash the broadcast loop; remaining clients continue receiving updates
  7. After a clean shutdown (Ctrl+C), logs/connections.ndjson and logs/alerts.ndjson contain all in-memory events that were not yet written
  8. Duplicate connections within a 1-second window appear as a single record with count > 1 in the NDJSON log
**Plans**: TBD

Plans:
- [ ] 05-01: In-memory store (bounded deques), NDJSON log writer with rotation, deduplication and event_id/severity fields; MET-01 metrics logger (packets/sec, drops, active connections every 5s)
- [ ] 05-02: FastAPI app with lifespan context manager; GET /connections, GET /alerts, GET /stats, GET /status endpoints
- [ ] 05-03: WebSocket manager (/ws/live) with 500ms batch timer, max-100-events cap, slow-client drop, and graceful shutdown flush; TEST-02 synthetic load generator script; PERF-01/02 validation
**UI hint**: no

### Phase 6: Frontend Dashboard
**Goal**: A browser-based dashboard connects to the backend WebSocket, displays a live connections table, an alerts panel with severity color coding, a connections-per-app chart, and a connections-per-second chart — all updated from delta pushes without full DOM re-renders
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08
**Success Criteria** (what must be TRUE):
  1. The dashboard shows a live table with columns Time, App, Domain, IP, Port, Protocol, Flag — rows appear within 1 second of a new connection being captured
  2. The alerts panel displays new alerts with color coding that distinguishes WARNING from ALERT severity
  3. The connections-per-app chart updates to reflect new connection counts without requiring a page refresh
  4. The connections-per-second line chart shows a rolling 60-second window that shifts forward in real time
  5. The capture status indicator shows "Active" or "Stopped" reflecting the current backend state
  6. Opening browser dev tools and watching the WebSocket frames confirms the table rows update incrementally, not by replacing the entire table HTML on each push
**Plans**: TBD

Plans:
- [ ] 06-01: HTML/CSS layout — connections table, alerts panel, status indicator (Bootstrap 5 CDN)
- [ ] 06-02: WebSocket client, delta-update table row injection, alert panel rendering, and pause/resume toggle (UI-08)
- [ ] 06-03: Chart.js 4.x connections-per-app chart and connections-per-second rolling line chart
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Capture Foundation | 1/3 | In Progress|  |
| 2. Process Attribution | 0/2 | Not started | - |
| 3. DNS Resolution | 0/2 | Not started | - |
| 4. Detection Engine | 0/2 | Not started | - |
| 5. Data Store and Backend API | 0/3 | Not started | - |
| 6. Frontend Dashboard | 0/3 | Not started | - |

**Total:** 67 requirements across 6 phases, 15 plans
