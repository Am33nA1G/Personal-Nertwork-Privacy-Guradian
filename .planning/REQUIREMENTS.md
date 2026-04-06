# Requirements: Personal Network Privacy Guardian (PNPG)

**Defined:** 2026-03-31
**Updated:** 2026-04-04 — PRD upgraded to production-grade; new enrichment, auth, allowlist, observability, and PostgreSQL requirements added
**Core Value:** Users can see exactly which apps are talking to the internet and get alerted when something looks suspicious — without needing to understand Wireshark.

## v1 Requirements

### Capture

- [x] **CAP-01**: System captures outgoing network packets in real-time using Scapy with `store=False` (no memory accumulation)
- [x] **CAP-02**: System runs Npcap startup check and exits with a clear error message if Npcap is not installed (Windows); checks for libpcap on Linux
- [x] **CAP-03**: System verifies it is running with administrator/root privileges on startup
- [x] **CAP-04**: System auto-selects the interface with highest outbound traffic if multiple interfaces are active
- [x] **CAP-05**: Packet sniffer runs in a dedicated daemon thread with a bounded asyncio queue (maxsize=500) bridging to FastAPI
- [x] **CAP-06**: When the packet queue reaches max capacity, system drops oldest packets (drop-head strategy) instead of blocking
- [x] **CAP-07**: System logs packet drops as INFO events for observability
- [x] **CAP-08**: Each event includes both wall-clock timestamp (ISO8601) and monotonic timestamp for accurate ordering
- [x] **CAP-09**: User can override interface selection via `config.yaml` or CLI flag
- [x] **CAP-10**: Packet sniffer automatically restarts on failure with exponential backoff

### Process Attribution

- [x] **PROC-01**: System maps each connection to an originating process name and PID using psutil
- [x] **PROC-02**: psutil connection table is polled on a background schedule (200ms interval) — not called per-packet
- [x] **PROC-03**: Connections that cannot be attributed show "unknown process" rather than failing or crashing
- [x] **PROC-04**: System handles `AccessDenied` from psutil for system processes gracefully
- [x] **PROC-05**: System correlates packet (src_ip, src_port) with psutil connection table using a lookup cache
- [x] **PROC-06**: Mapping cache entries expire after configurable TTL (default: 2 seconds) to prevent stale attribution

### DNS Resolution

- [ ] **DNS-01**: System resolves destination IPs to domain names via reverse DNS lookup
- [ ] **DNS-02**: DNS lookups run in a thread pool executor (not blocking the event loop)
- [ ] **DNS-03**: DNS resolution has a 2-second timeout per lookup to prevent pipeline stall
- [ ] **DNS-04**: Resolved IP→domain mappings are cached with TTL to avoid repeated lookups for the same destination
- [ ] **DNS-05**: Unresolvable IPs fall back to displaying raw IP address
- [ ] **DNS-06**: DNS cache is bounded to a maximum of 1000 entries with LRU eviction to prevent unbounded memory growth

### GeoIP & ASN Enrichment

- [ ] **GEO-01**: System resolves destination IPs to country codes using a local MaxMind GeoLite2 database (no external network call)
- [ ] **GEO-02**: System resolves destination IPs to ASN and organization name using a local ASN database
- [ ] **GEO-03**: GeoIP lookups have a hard timeout of 5ms (local DB — fast path only)
- [ ] **GEO-04**: Failed GeoIP/ASN lookups return `null` for those fields — the pipeline never blocks waiting for geo data
- [ ] **GEO-05**: System logs a `GEOIP_STALE` metric if the local GeoIP database is older than 30 days

### Threat Intelligence

- [ ] **THREAT-01**: System checks each connection's dst_ip and dst_domain against a local threat intelligence blocklist
- [ ] **THREAT-02**: Threat intel blocklist is stored locally and never requires an external network call during runtime
- [ ] **THREAT-03**: Blocklist check has a hard timeout of 5ms — never blocks the pipeline
- [ ] **THREAT-04**: System logs a `THREATINTEL_STALE` metric if the local blocklist has not been updated in more than 24 hours
- [ ] **THREAT-05**: System flags blocklisted destinations with `threat_intel.is_blocklisted: true` and records the source list name

### Detection

- [ ] **DET-01**: System flags connections with no resolvable domain as WARNING
- [ ] **DET-02**: System flags a process exceeding 100 connections per minute as HIGH severity (rate spike)
- [ ] **DET-03**: System flags connections on unusual ports from a process only when combined with unknown process or abnormal frequency (reduces false positives)
- [ ] **DET-04**: System flags connections from an "unknown process" (PID unresolvable) as ALERT
- [ ] **DET-05**: System flags connections to any blocklisted IP or domain as CRITICAL (requires THREAT-01)
- [ ] **DET-06**: System flags connections to TOR exit nodes as HIGH severity
- [ ] **DET-07**: System flags the first-ever external destination for a process as LOW (new destination discovery)
- [ ] **DET-08**: Detection thresholds (rate limit, port allowlist) are named constants from `config.yaml` — no magic numbers in detection code
- [ ] **DET-09**: Detection engine rate-limits alerts to max 1 alert per rule per process per second to prevent alert flooding
- [ ] **DET-10**: All generated alerts include: alert_id, timestamp, severity, rule_id, reason, confidence, process_name, pid, dst_ip, dst_hostname, recommended_action, suppressed

### Allowlist Management

- [ ] **ALLOW-01**: User can create an allowlist rule scoped to a specific process + destination (IP or domain)
- [ ] **ALLOW-02**: User can create a global allowlist rule that applies to all processes for a given destination
- [ ] **ALLOW-03**: Allowlist rules can have an optional expiry timestamp (null = permanent)
- [ ] **ALLOW-04**: The detection engine checks the allowlist before emitting an alert — matching rules suppress the alert
- [ ] **ALLOW-05**: Allowlist rules persist in PostgreSQL (survive restarts)
- [ ] **ALLOW-06**: API supports GET /api/v1/allowlist, POST /api/v1/allowlist, DELETE /api/v1/allowlist/:rule_id

### Alert Suppression

- [ ] **SUPP-01**: User can suppress a single alert instance ("dismiss this one")
- [ ] **SUPP-02**: User can suppress all future alerts from a specific rule for a specific process
- [ ] **SUPP-03**: Suppressions are persisted in PostgreSQL with created_at, rule_id, process_name (nullable), scope, reason
- [x] **SUPP-04**: A suppression log is viewable in the dashboard with the ability to undo any suppression
- [ ] **SUPP-05**: API supports PATCH /api/v1/alerts/:alert_id with action "suppress" or "resolve"

### Storage

- [ ] **STORE-01**: Connection events are written to a PostgreSQL `connections` table with 30-day default retention
- [ ] **STORE-02**: Alert events are written to a PostgreSQL `alerts` table with 90-day default retention
- [ ] **STORE-03**: A `processes` registry table tracks process name, path, first_seen, last_seen (retained indefinitely)
- [ ] **STORE-04**: An `allowlist` table stores user-defined allow rules (retained indefinitely)
- [ ] **STORE-05**: Connection events are also written to `logs/connections.ndjson` in NDJSON format as a lightweight audit log
- [ ] **STORE-06**: Alert events are also written to `logs/alerts.ndjson` in NDJSON format
- [ ] **STORE-07**: NDJSON log files rotate or cap at a configurable size to prevent unbounded disk growth
- [ ] **STORE-08**: Each connection event includes a unique `event_id` (UUID) for traceability
- [ ] **STORE-09**: Each event includes a `severity` field (INFO, WARNING, ALERT, CRITICAL)
- [ ] **STORE-10**: Database indexes on `connections(timestamp, process_name)`, `connections(dst_ip)`, `alerts(timestamp, severity)` for query performance
- [ ] **STORE-11**: Automatic nightly purge of data outside the configured retention window

### Authentication

- [x] **AUTH-01**: POST /api/v1/auth/login accepts a password and returns a signed JWT (HS256, 8-hour expiry) and a refresh token
- [ ] **AUTH-02**: All REST API endpoints require a valid JWT in the Authorization header; returns 401 if missing or invalid
- [ ] **AUTH-03**: WebSocket /api/v1/ws/live authenticates via `?token=<jwt>` query parameter
- [x] **AUTH-04**: Dashboard password is set during the first-run setup wizard and stored as a bcrypt hash

### Backend API

- [ ] **API-01**: `GET /api/v1/connections` returns paginated connection history; supports filters: from, to, process, dst_ip, page, page_size
- [ ] **API-02**: `GET /api/v1/alerts` returns paginated alerts; supports filters: status (active/suppressed/resolved), severity, from, to
- [ ] **API-03**: `GET /api/v1/stats/summary` returns: total_connections, unique_destinations, active_alerts, top_processes, top_destinations for last 24h
- [ ] **API-04**: `GET /api/v1/stats/timeseries` returns time-bucketed metric data; supports: metric (connections/bytes/alerts), interval (1m/5m/1h/1d), from, to
- [ ] **API-05**: `GET /api/v1/status` returns capture state (running/stopped), interface name, uptime, probe type (ebpf/libpcap)
- [ ] **API-06**: `WebSocket /api/v1/ws/live` pushes batched updates (connection events and alerts) every 500ms; also emits heartbeat every 10s
- [ ] **API-07**: WebSocket supports client-sent filter messages: `{ "type": "filter", "data": { "process": "chrome" } }`
- [ ] **API-08**: WebSocket manager handles client disconnections without crashing the broadcast loop
- [ ] **API-09**: FastAPI app uses lifespan context manager (not deprecated `on_event`) to start/stop the sniffer thread
- [ ] **API-10**: WebSocket batches are capped at a maximum of 100 events per push; slow clients are dropped
- [ ] **API-11**: Rate limiting: 100 REST requests per minute per client; authenticated WebSocket streams are unlimited
- [ ] **API-12**: `GET /api/v1/health` returns: status, probe type (ebpf/libpcap/down), db status, stream status
- [ ] **API-13**: All API responses use consistent envelope: `{ "data": ..., "pagination": ... }` for list responses

### Pipeline Worker

- [x] **PIPE-01**: A dedicated async pipeline worker consumes packets from the queue and processes each event sequentially through: Analyzer → Process Mapper → DNS Resolver → Enrichment (GeoIP/ASN/ThreatIntel) → Detection Engine → Storage → WebSocket push
- [x] **PIPE-02**: Pipeline worker preserves packet order — events are processed in the order they are dequeued
- [x] **PIPE-03**: Pipeline worker never blocks on DNS or process mapping — all blocking calls dispatched to thread pool executors

### Performance

- [ ] **PERF-01**: System sustains at least 10,000 events/sec with fewer than 2% event drop under sustained load
- [ ] **PERF-02**: End-to-end latency from packet capture to dashboard display is less than 100ms (p95)
- [ ] **PERF-03**: Total system CPU overhead stays below 10%; hard limit 18%
- [ ] **PERF-04**: Total memory footprint stays below 2GB; hard limit 3GB

### Observability

- [ ] **OBS-01**: System exposes a Prometheus-compatible `/metrics` endpoint with counters: events_captured_total, events_dropped_total, alerts_generated_total
- [ ] **OBS-02**: System exposes Prometheus histograms: enrichment_latency_ms (per lookup type), db_write_latency_ms
- [ ] **OBS-03**: System exposes Prometheus gauges: stream_consumer_lag, probe_status (1=eBPF, 0.5=libpcap, 0=down)
- [ ] **OBS-04**: System logs packets/sec, dropped packet count, and active connection count every 5 seconds at INFO level
- [ ] **OBS-05**: All components emit structured JSON logs with level, timestamp, component, and message fields
- [ ] **OBS-06**: Log rotation: 100MB max per file, 7-day retention; stored in `/var/log/pnpg/` (Linux) or `logs/` (Windows)

### Deployment

- [ ] **DEPLOY-01**: Application ships with a Docker Compose file defining all services: pnpg-probe, pnpg-collector, pnpg-redis, pnpg-enrichment, pnpg-detection, pnpg-postgres, pnpg-api, pnpg-dashboard, pnpg-nginx
- [ ] **DEPLOY-02**: Each service has defined liveness and readiness health checks
- [ ] **DEPLOY-03**: Environment variables documented; no secrets hardcoded in Docker Compose or source code

### Testing & Observability

- [x] **TEST-01**: Debug mode (enabled via config.yaml flag) prints each enriched pipeline event to console for validation during development
- [ ] **TEST-02**: Synthetic traffic generator script produces rapid HTTP requests to simulate load for testing PERF-01/02

### Configuration

- [x] **CONFIG-01**: All thresholds and runtime settings stored in `config.yaml` (queue size, polling interval, alert rate limit, port allowlist, log rotation size)
- [x] **CONFIG-02**: Config is validated at startup with sensible defaults applied for any missing keys
- [x] **CONFIG-03**: System logs all critical errors without terminating the main event loop

### System Reliability

- [x] **SYS-01**: System logs all critical errors without terminating the main event loop
- [ ] **SYS-02**: Graceful shutdown flushes all in-memory data to disk before exit
- [ ] **SYS-03**: If the eBPF probe fails, system automatically falls back to libpcap with a non-alarming notice in the dashboard
- [ ] **SYS-04**: If PostgreSQL is unavailable, API returns 503 and events queue in the stream layer until storage recovers

### Frontend Dashboard

- [x] **UI-01**: Live connections table with columns: Time, App, Domain, Country, IP, Port, Protocol, Flag
- [x] **UI-02**: Alerts panel displaying active alerts with severity color coding (WARNING=yellow, ALERT=orange, CRITICAL=red)
- [ ] **UI-03**: Chart: connections per app (bar or donut) — using Recharts
- [ ] **UI-04**: Chart: connections per second over time (line chart, rolling 60s window) — using Recharts
- [ ] **UI-05**: Capture status indicator showing whether sniffing is active and which capture method is in use (eBPF/libpcap)
- [x] **UI-06**: Frontend connects to WebSocket and updates table/charts on each batch push (delta updates only, no full DOM re-render)
- [x] **UI-07**: Dashboard has a pause/resume toggle that halts live UI updates for inspection without disconnecting the WebSocket
- [x] **UI-08**: Alerts panel supports suppress and resolve actions per alert
- [ ] **UI-09**: Allowlist Manager screen: view all rules, add new rules (process/domain/IP scoped), delete rules
- [x] **UI-10**: Dashboard reconnects to WebSocket with exponential backoff (max 30s) and shows a connection status indicator
- [x] **UI-11**: Built with React 18 / Next.js 14 — served from the same Docker Compose stack

---

## v2 Requirements

### Behavioral Detection (V2)

- **BDET-01**: Per-process rolling behavioral baseline (destination IPs, ports, data volume, connection frequency) over a 7-day window
- **BDET-02**: Deviation scoring using z-score against the 7-day baseline
- **BDET-03**: Time-of-day awareness — separate baselines for business hours vs off-hours
- **BDET-04**: Minimum 48 hours of history required before behavioral alerts are enabled for a process
- **BDET-05**: Data volume spike detection: flag when a process exceeds 3× its 7-day average bytes sent

### Advanced Analytics (V2)

- **ANL-01**: Baseline Explorer screen: per-process behavioral baseline visualization
- **ANL-02**: Export connections to CSV from the dashboard

### UI Enhancements (V2)

- **UIX-01**: Filter connections by app, domain, or protocol in the live table
- **UIX-02**: Click a connection to see detailed view with all attributes including GeoIP and ASN
- **UIX-03**: Dark mode support

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| Firewall / packet blocking | OS-level enforcement, requires kernel drivers — beyond scope |
| HTTPS payload decryption | Requires MITM certificate injection — security risk and legal complexity |
| Cloud-based monitoring or remote data collection | Runs locally only by design; no external data sharing |
| Mobile app | Web dashboard is sufficient for local monitoring use case |
| Multi-user access (teams) | V2 — local single-user tool for now |
| Inbound traffic monitoring | Scope is outgoing traffic; bidirectional adds complexity for limited value |
| Enterprise SIEM replacement | Not a goal for this product |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CAP-01 | Phase 1 | Complete |
| CAP-02 | Phase 1 | Complete |
| CAP-03 | Phase 1 | Complete |
| CAP-04 | Phase 1 | Complete |
| CAP-05 | Phase 1 | Complete |
| CAP-06 | Phase 1 | Complete |
| CAP-07 | Phase 1 | Complete |
| CAP-08 | Phase 1 | Complete |
| CAP-09 | Phase 1 | Complete |
| CAP-10 | Phase 1 | Complete |
| PROC-01 | Phase 2 | Complete |
| PROC-02 | Phase 2 | Complete |
| PROC-03 | Phase 2 | Complete |
| PROC-04 | Phase 2 | Complete |
| PROC-05 | Phase 2 | Complete |
| PROC-06 | Phase 2 | Complete |
| DNS-01 | Phase 3 | Pending |
| DNS-02 | Phase 3 | Pending |
| DNS-03 | Phase 3 | Pending |
| DNS-04 | Phase 3 | Pending |
| DNS-05 | Phase 3 | Pending |
| DNS-06 | Phase 3 | Pending |
| GEO-01 | Phase 3 | Pending |
| GEO-02 | Phase 3 | Pending |
| GEO-03 | Phase 3 | Pending |
| GEO-04 | Phase 3 | Pending |
| GEO-05 | Phase 3 | Pending |
| THREAT-01 | Phase 3 | Pending |
| THREAT-02 | Phase 3 | Pending |
| THREAT-03 | Phase 3 | Pending |
| THREAT-04 | Phase 3 | Pending |
| THREAT-05 | Phase 3 | Pending |
| DET-01 | Phase 4 | Pending |
| DET-02 | Phase 4 | Pending |
| DET-03 | Phase 4 | Pending |
| DET-04 | Phase 4 | Pending |
| DET-05 | Phase 4 | Pending |
| DET-06 | Phase 4 | Pending |
| DET-07 | Phase 4 | Pending |
| DET-08 | Phase 4 | Pending |
| DET-09 | Phase 4 | Pending |
| DET-10 | Phase 4 | Pending |
| ALLOW-01 | Phase 4 | Pending |
| ALLOW-02 | Phase 4 | Pending |
| ALLOW-03 | Phase 4 | Pending |
| ALLOW-04 | Phase 4 | Pending |
| ALLOW-05 | Phase 5 | Pending |
| ALLOW-06 | Phase 5 | Pending |
| SUPP-01 | Phase 4 | Pending |
| SUPP-02 | Phase 4 | Pending |
| SUPP-03 | Phase 5 | Pending |
| SUPP-04 | Phase 6 | Complete |
| SUPP-05 | Phase 5 | Pending |
| STORE-01 | Phase 5 | Pending |
| STORE-02 | Phase 5 | Pending |
| STORE-03 | Phase 5 | Pending |
| STORE-04 | Phase 5 | Pending |
| STORE-05 | Phase 5 | Pending |
| STORE-06 | Phase 5 | Pending |
| STORE-07 | Phase 5 | Pending |
| STORE-08 | Phase 5 | Pending |
| STORE-09 | Phase 5 | Pending |
| STORE-10 | Phase 5 | Pending |
| STORE-11 | Phase 5 | Pending |
| AUTH-01 | Phase 5 | Complete |
| AUTH-02 | Phase 5 | Pending |
| AUTH-03 | Phase 5 | Pending |
| AUTH-04 | Phase 5 | Complete |
| API-01 | Phase 5 | Pending |
| API-02 | Phase 5 | Pending |
| API-03 | Phase 5 | Pending |
| API-04 | Phase 5 | Pending |
| API-05 | Phase 5 | Pending |
| API-06 | Phase 5 | Pending |
| API-07 | Phase 5 | Pending |
| API-08 | Phase 5 | Pending |
| API-09 | Phase 5 | Pending |
| API-10 | Phase 5 | Pending |
| API-11 | Phase 5 | Pending |
| API-12 | Phase 5 | Pending |
| API-13 | Phase 5 | Pending |
| PIPE-01 | Phase 1 | Complete |
| PIPE-02 | Phase 1 | Complete |
| PIPE-03 | Phase 1 | Complete |
| PERF-01 | Phase 7 | Pending |
| PERF-02 | Phase 7 | Pending |
| PERF-03 | Phase 7 | Pending |
| PERF-04 | Phase 7 | Pending |
| OBS-01 | Phase 7 | Pending |
| OBS-02 | Phase 7 | Pending |
| OBS-03 | Phase 7 | Pending |
| OBS-04 | Phase 5 | Pending |
| OBS-05 | Phase 7 | Pending |
| OBS-06 | Phase 7 | Pending |
| DEPLOY-01 | Phase 7 | Pending |
| DEPLOY-02 | Phase 7 | Pending |
| DEPLOY-03 | Phase 7 | Pending |
| TEST-01 | Phase 1 | Complete |
| TEST-02 | Phase 5 | Pending |
| CONFIG-01 | Phase 1 | Complete |
| CONFIG-02 | Phase 1 | Complete |
| CONFIG-03 | Phase 1 | Complete |
| SYS-01 | Phase 1 | Complete |
| SYS-02 | Phase 5 | Pending |
| SYS-03 | Phase 3 | Pending |
| SYS-04 | Phase 5 | Pending |
| UI-01 | Phase 6 | Complete |
| UI-02 | Phase 6 | Complete |
| UI-03 | Phase 6 | Pending |
| UI-04 | Phase 6 | Pending |
| UI-05 | Phase 6 | Pending |
| UI-06 | Phase 6 | Complete |
| UI-07 | Phase 6 | Complete |
| UI-08 | Phase 6 | Complete |
| UI-09 | Phase 6 | Pending |
| UI-10 | Phase 6 | Complete |
| UI-11 | Phase 6 | Complete |

**Coverage:**
- v1 requirements: 107 total (was 67 — +40 from PRD upgrade)
- Mapped to phases: 107
- Unmapped: 0 ✓

---

## Data Model

### Connection Object (Production Schema)
```json
{
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "process_name": "chrome.exe",
  "process_path": "/usr/bin/google-chrome",
  "pid": 1234,
  "uid": 1000,
  "src_ip": "192.168.1.5",
  "src_port": 52341,
  "dst_ip": "142.250.183.14",
  "dst_hostname": "google.com",
  "dst_country": "US",
  "dst_asn": "AS15169",
  "dst_org": "Google LLC",
  "dst_port": 443,
  "protocol": "TCP",
  "bytes_sent": 1240,
  "bytes_recv": 8800,
  "state": "ESTABLISHED",
  "threat_intel": {
    "is_blocklisted": false,
    "source": null
  },
  "severity": "INFO"
}
```

### Alert Object (Production Schema)
```json
{
  "alert_id": "uuid",
  "timestamp": "ISO8601",
  "severity": "HIGH",
  "rule_id": "DET-02",
  "reason": "chrome exceeded 100 connections/min to 45 unique destinations",
  "confidence": 0.91,
  "process_name": "chrome",
  "pid": 4821,
  "dst_ip": "93.184.216.34",
  "dst_hostname": "example.com",
  "recommended_action": "REVIEW",
  "suppressed": false
}
```

---

## Known Limitations

- Packet-to-process mapping is best-effort; very short-lived connections may not be attributable
- Reverse DNS may not resolve all IPs accurately (no PTR records)
- Byte tracking is approximate (packet-level, not full TCP stream reconstruction)
- High traffic environments may result in dropped packets due to bounded queue backpressure
- GeoIP accuracy is limited by the MaxMind GeoLite2 database (free tier)
- Behavioral detection (V2) requires 48h of history per process before alerts are meaningful
- Windows support is partial in V1 (no eBPF; process mapping via Win32 API has limitations)

---
*Requirements defined: 2026-03-31*
*Last updated: 2026-04-04 — PRD upgraded to production-grade v1.0; 40 new requirements added across GeoIP, ASN, Threat Intel, Allowlist, Alert Suppression, Authentication, PostgreSQL, Prometheus, and Docker Compose sections; detection rules expanded from 6 to 10 (R001-R007 equivalent); performance target updated from 500/sec to 10,000/sec; frontend updated from Vanilla JS to React 18/Next.js 14 + Recharts; coverage updated from 67 to 107 requirements*
