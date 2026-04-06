# Roadmap: Personal Network Privacy Guardian (PNPG)

## Overview

Seven phases that build the PNPG pipeline from the ground up in dependency order: first establish the threading architecture that everything else relies on (Phase 1), then add process attribution as the first enrichment layer (Phase 2), then resolve destinations to hostname/country/ASN and check threat intel (Phase 3), then apply 10 detection rules with allowlist suppression (Phase 4), then wire up PostgreSQL storage and the versioned JWT-authenticated API (Phase 5), then build the React dashboard with alert management and Allowlist Manager (Phase 6), and finally package everything into Docker Compose with Prometheus/Grafana observability and load-test at 10,000 events/sec (Phase 7). No phase is optional; each is a prerequisite for the next.

> **Updated 2026-04-04:** PRD upgraded to production-grade. Phases 3-7 restructured vs original 6-phase plan.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Capture Foundation** - Establish the Scapy threading architecture, Windows prerequisites, and async queue bridge that all subsequent phases depend on (completed 2026-04-01)
- [x] **Phase 2: Process Attribution** - Enrich captured packets with originating process name and PID using a psutil polling cache (completed 2026-04-04)
> **PRD Upgrade Note (2026-04-04):** The PRD was upgraded to a production-grade system. Phases 1-2 remain valid. Phases 3-7 have been restructured to reflect: PostgreSQL storage, GeoIP/ASN/threat-intel enrichment, 10 detection rules with allowlist suppression, React/Next.js 14 frontend, JWT auth, and Docker Compose deployment with Prometheus/Grafana observability.

- [x] **Phase 3: Enrichment Service** - Resolve destination IPs to domain names, country, ASN; check against a local threat intelligence blocklist; all enrichment non-blocking with hard timeouts (completed 2026-04-05)
- [x] **Phase 4: Detection Engine** - Apply 10 rule-based detection rules (DET-01 to DET-10) against fully enriched events; structured alerts; allowlist check before firing; per-rule rate limiting (completed 2026-04-05)
- [x] **Phase 5: Data Store and Backend API** - Persist events to PostgreSQL; versioned FastAPI REST (/api/v1/) with JWT auth, pagination, rate limiting, allowlist CRUD, alert suppression, WebSocket live stream (completed 2026-04-05)
- [ ] **Phase 6: Frontend Dashboard** - React 18 / Next.js 14 dashboard; live connections table, alerts panel with suppress/resolve, Recharts charts, Allowlist Manager screen
- [ ] **Phase 7: Deployment & Observability** - Docker Compose stack; Prometheus metrics; Grafana dashboards; health endpoints; 10,000 events/sec load test

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
- [x] 01-02-PLAN.md — Scapy sniffer daemon thread, interface auto-selection, asyncio queue bridge with drop-head
- [x] 01-03-PLAN.md — Sniffer supervisor with exponential backoff restart, async pipeline worker, FastAPI lifespan

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
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md — Wave 0 test stubs + process_mapper.py (cache, poller, enrich_event)
- [x] 02-02-PLAN.md — Field extraction in queue_bridge (D-01/D-02/D-03), worker integration, lifespan wiring

### Phase 3: Enrichment Service
**Goal**: Every connection event is enriched with: (1) a reverse-DNS hostname, (2) country + ASN from a local GeoIP database, (3) a threat intelligence blocklist check — all lookups are non-blocking, have hard timeouts, are cached, and degrade gracefully to null rather than stalling the pipeline
**Depends on**: Phase 2
**Requirements**: DNS-01, DNS-02, DNS-03, DNS-04, DNS-05, DNS-06, GEO-01, GEO-02, GEO-03, GEO-04, GEO-05, THREAT-01, THREAT-02, THREAT-03, THREAT-04, THREAT-05, SYS-03
**Success Criteria** (what must be TRUE):
  1. Connection events for well-known destinations (e.g., google.com) show the domain name, country, and ASN in pipeline output
  2. An IP with no PTR record resolves to the raw IP string within 2 seconds — the pipeline does not stall
  3. DNS lookups never run on the asyncio event loop — event loop remains unblocked during a burst of new IPs
  4. The same IP is not looked up twice within its TTL window — log shows cache hit for repeated destinations
  5. A destination IP on the local blocklist produces `threat_intel.is_blocklisted: true` in the enriched event
  6. If the GeoIP database is missing, the pipeline continues with null geo fields and logs a GEOIP_STALE warning
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Thread pool DNS resolver with TTL+LRU cache (DNS-01 to DNS-06)
- [x] 03-02-PLAN.md — GeoIP + ASN enrichment with MaxMind GeoLite2 (GEO-01 to GEO-05)
- [x] 03-03-PLAN.md — Threat intel blocklist + wire all enrichment into pipeline (THREAT-01 to THREAT-05, SYS-03)

### Phase 4: Detection Engine
**Goal**: Fully enriched connection events are evaluated against 10 detection rules (DET-01 to DET-10: unknown domain, rate spike, unusual port, unknown process, blocklisted IP, TOR exit node, new destination discovery); the allowlist is checked before any alert is emitted; alert flooding is rate-limited to 1 per rule per process per second
**Depends on**: Phase 3
**Requirements**: DET-01, DET-02, DET-03, DET-04, DET-05, DET-06, DET-07, DET-08, DET-09, DET-10, ALLOW-01, ALLOW-02, ALLOW-03, ALLOW-04, SUPP-01, SUPP-02
**Success Criteria** (what must be TRUE):
  1. A connection with no resolvable domain emits a WARNING alert in the alert stream
  2. Sending more than 100 connections per minute from a single process triggers a DET-02 HIGH alert
  3. A connection on an unusual port from an unknown process emits an alert; same port from a known process at normal frequency does not (false-positive gate confirmed)
  4. A connection from "unknown process" emits a DET-04 ALERT
  5. A destination IP on the threat intel blocklist emits a DET-05 CRITICAL alert
  6. A connection to a TOR exit node IP emits a DET-06 HIGH alert
  7. The first-ever destination for a process emits a DET-07 LOW discovery alert
  8. When a rule fires continuously, no more than 1 alert per rule per process per second appears (rate limiter confirmed by log count)
  9. A connection matching an allowlist rule produces no alert (suppression confirmed in log)
  10. All thresholds are read from config.yaml named constants — no magic numbers in detection code
**Plans**: TBD

Plans:
- [x] 04-01: Detection rule implementations DET-01 to DET-07, DET-09 using named constants from config; in-memory first-seen tracker for DET-07
- [x] 04-02: Per-rule per-process rate limiter (DET-09), structured alert object construction with all fields (DET-10), allowlist pre-check (ALLOW-02 to ALLOW-04), in-memory suppression store (SUPP-01, SUPP-02)

### Phase 5: Data Store and Backend API
**Goal**: Connection and alert events are persisted to PostgreSQL with indexed tables; NDJSON files serve as append-only audit logs; FastAPI exposes versioned REST endpoints (/api/v1/) with JWT authentication, pagination, allowlist CRUD, and alert suppression; WebSocket batches updates every 500ms; graceful shutdown flushes in-memory state to disk
**Depends on**: Phase 4
**Requirements**: STORE-01, STORE-02, STORE-03, STORE-04, STORE-05, STORE-06, STORE-07, STORE-08, STORE-09, STORE-10, STORE-11, AUTH-01, AUTH-02, AUTH-03, AUTH-04, API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08, API-09, API-10, API-11, API-12, API-13, ALLOW-05, ALLOW-06, SUPP-03, SUPP-04, SUPP-05, OBS-04, SYS-02, SYS-04, TEST-02
**Success Criteria** (what must be TRUE):
  1. GET /api/v1/connections returns paginated JSON with connection objects including domain, country, ASN, and threat_intel fields
  2. POST /api/v1/auth/login returns a JWT; subsequent requests without a valid JWT return 401
  3. GET /api/v1/alerts returns active alerts; PATCH /api/v1/alerts/:id with action "suppress" marks the alert suppressed
  4. GET /api/v1/stats/summary returns total_connections, unique_destinations, active_alerts, top_processes for last 24h
  5. GET /api/v1/allowlist returns all rules; POST creates one; DELETE removes one by rule_id
  6. WebSocket /api/v1/ws/live receives batched pushes every 500ms (not per-packet); heartbeat every 10s
  7. Disconnecting a WebSocket client does not crash the broadcast loop
  8. After clean shutdown, all in-memory events are flushed to NDJSON logs and PostgreSQL before exit
  9. System logs packets/sec, drops, and active connection count every 5 seconds (OBS-04)
**Plans**: TBD

Plans:
- [x] 05-01: PostgreSQL schema (connections, alerts, processes, allowlist, suppressions tables) with indexes; NDJSON log writer with rotation; OBS-04 metrics logger
- [x] 05-02: JWT auth (login endpoint, token validation middleware, password bcrypt hashing); all REST endpoints under /api/v1/ with pagination and filters
- [x] 05-03: WebSocket manager (/api/v1/ws/live) with 500ms batch timer, client filter support, slow-client drop, graceful shutdown flush; TEST-02 synthetic load generator; SYS-02/SYS-04 reliability
**UI hint**: no

### Phase 6: Frontend Dashboard
**Goal**: A React 18 / Next.js 14 dashboard connects to the backend WebSocket, displays a live connections table (with country + ASN columns), an alerts panel with suppress/resolve actions, Recharts data visualisation (connections-per-app, connections-per-second), an Allowlist Manager, and a capture status indicator — all updated from delta pushes without full re-renders
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09, UI-10, UI-11, SUPP-04
**Success Criteria** (what must be TRUE):
  1. Dashboard shows a live table with columns Time, App, Domain, Country, IP, Port, Protocol, Flag — rows appear within 1 second of a new connection being captured
  2. Alerts panel displays new alerts with severity color coding (WARNING/ALERT/CRITICAL); each alert has Suppress and Resolve buttons that call the API
  3. Connections-per-app chart (Recharts) updates to reflect new counts without page refresh
  4. Connections-per-second line chart (Recharts) shows a rolling 60-second window that shifts forward in real time
  5. Capture status indicator shows Active/Stopped and capture method (eBPF/libpcap)
  6. Allowlist Manager screen shows all rules; user can add a new rule (process-scoped or global) and delete existing rules
  7. WebSocket reconnects with exponential backoff (max 30s) and shows a reconnecting status indicator
  8. Browser dev tools confirm table rows update incrementally (delta), not by replacing the full table on each push
**Plans**: TBD

Plans:
- [x] 06-01: Next.js 14 project scaffold with Bootstrap 5 layout; live connections table component with delta-update row injection; WebSocket client with exponential backoff reconnect (UI-01, UI-06, UI-07, UI-10, UI-11)
- [x] 06-02: Alerts panel component with severity color coding, Suppress and Resolve actions wired to API; pause/resume toggle (UI-02, UI-07, UI-08, SUPP-04)
- [ ] 06-03: Recharts connections-per-app bar/donut chart; connections-per-second rolling line chart; capture status indicator; Allowlist Manager screen (UI-03, UI-04, UI-05, UI-09)
**UI hint**: yes

### Phase 7: Deployment & Observability
**Goal**: The full application runs as a Docker Compose stack; Prometheus metrics are exposed and scraped; pre-built Grafana dashboards show event throughput, consumer lag, alert rate, and enrichment latency; health endpoints are live; the system passes a 10-minute sustained 10,000 events/sec load test without dropping more than 2% of events
**Depends on**: Phase 6
**Requirements**: PERF-01, PERF-02, PERF-03, PERF-04, OBS-01, OBS-02, OBS-03, OBS-05, OBS-06, DEPLOY-01, DEPLOY-02, DEPLOY-03
**Success Criteria** (what must be TRUE):
  1. `docker compose up` starts all services and the dashboard is accessible at http://localhost:7070 within 30 seconds
  2. GET /api/v1/health returns `{ "status": "ok", "probe": "libpcap", "db": "ok" }`
  3. GET /metrics returns Prometheus metrics including events_captured_total, events_dropped_total, enrichment_latency_ms, alerts_generated_total
  4. Grafana dashboard shows live data from Prometheus (event throughput, alert rate, enrichment latency)
  5. Load test at 10,000 synthetic events/sec sustained for 10 minutes: event drop rate < 2%, p95 end-to-end latency < 100ms
  6. All services restart automatically on crash (liveness probes confirmed in compose health checks)
**Plans**: TBD

Plans:
- [ ] 07-01: Prometheus /metrics endpoint integration across all services; structured JSON logging to /var/log/pnpg/; OBS-01 to OBS-06
- [ ] 07-02: Docker Compose file with all 9 services, health checks, and environment variable config; DEPLOY-01 to DEPLOY-03
- [ ] 07-03: Pre-built Grafana dashboard JSON; GET /api/v1/health endpoint; TEST-02 load test at 10,000 events/sec; PERF-01 to PERF-04 validation
**UI hint**: no

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Capture Foundation | 3/3 | Complete   | 2026-04-01 |
| 2. Process Attribution | 2/2 | Complete   | 2026-04-04 |
| 3. Enrichment Service | 3/3 | Complete | 2026-04-05 |
| 4. Detection Engine | 2/2 | Complete | 2026-04-05 |
| 5. Data Store and Backend API | 3/3 | Complete   | 2026-04-05 |
| 6. Frontend Dashboard | 2/3 | In Progress|  |
| 7. Deployment & Observability | 0/3 | Not started | - |

**Total:** 107 requirements across 7 phases, 19 plans
