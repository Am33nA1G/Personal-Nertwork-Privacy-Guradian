# Personal Network Privacy Guardian (PNPG)
### Production-Grade Product Requirements Document
**Version:** 1.0 | **Status:** Approved — Ready for Engineering | **Classification:** Confidential

---

## Document Metadata

| Field | Value |
|---|---|
| Document Owner | Engineering Lead / Product |
| Status | APPROVED — Ready for Engineering |
| Target MVP Date | Q3 2025 |
| Target V1 (Production) Date | Q1 2026 |
| Revision | 1.0 |
| Classification | Confidential — Internal Use Only |

---

## Table of Contents

1. [Vision](#1-vision)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Target Users](#3-target-users)
4. [Key Problems](#4-key-problems)
5. [High-Level Solution](#5-high-level-solution)
6. [System Architecture](#6-system-architecture)
7. [Core Components](#7-core-components)
8. [API Contract](#8-api-contract)
9. [Privilege & Trust Model](#9-privilege--trust-model)
10. [Data Retention & Privacy Policy](#10-data-retention--privacy-policy)
11. [Failure Modes & Recovery](#11-failure-modes--recovery)
12. [False Positive Handling & Alert UX](#12-false-positive-handling--alert-ux)
13. [Onboarding & Installer Flow](#13-onboarding--installer-flow)
14. [Data Flow](#14-data-flow)
15. [Scalability Strategy](#15-scalability-strategy)
16. [Security Considerations](#16-security-considerations)
17. [Observability](#17-observability)
18. [Deployment Architecture](#18-deployment-architecture)
19. [Cross-Platform Strategy](#19-cross-platform-strategy)
20. [Performance Requirements](#20-performance-requirements)
21. [Testing Strategy](#21-testing-strategy)
22. [MVP vs Production Roadmap](#22-mvp-vs-production-roadmap)
23. [Risks & Mitigations](#23-risks--mitigations)
24. [Success Metrics](#24-success-metrics)

---

## 1. Vision

Build a **high-performance, privacy-first network observability platform** that provides real-time visibility into application-level network activity, detects anomalies, and empowers users to understand and control outbound data flows from their own machines.

> **Core Principle:** PNPG runs entirely locally. No telemetry, no cloud sync, no data leaves the host unless the user explicitly configures it.

---

## 2. Goals & Non-Goals

### Goals

- Real-time network monitoring with minimal system overhead
- Accurate process-to-network mapping (PID → process name → connection)
- Low false-positive anomaly detection (<10% false positive rate)
- Scalable architecture for high-throughput environments (≥10,000 events/sec)
- Cross-platform support: Linux (full), Windows (partial), macOS (limited)
- User-controlled allowlisting and alert tuning
- Transparent privilege model with explicit user consent

### Non-Goals

- Full antivirus or EDR replacement
- Deep packet inspection of encrypted payloads
- Enterprise SIEM replacement (initial versions)
- Cloud-based monitoring or remote data collection of any kind

---

## 3. Target Users

| Persona | Primary Need | Key Concern |
|---|---|---|
| Developer / Power User | Understand what their apps phone home to | Complexity — needs signal without noise |
| Security Enthusiast | Deep visibility into process-level activity | Accuracy, low false positives |
| Privacy-Conscious Individual | Block background data exfiltration | Ease of use, trust in the tool |
| Small Team / Indie Hacker | Lightweight alternative to enterprise tools | Cost, self-hostability |

---

## 4. Key Problems

- No easy visibility into which applications send data externally
- Existing tools (Wireshark, netstat) are too low-level for non-experts
- Antivirus products lack process-level network transparency
- Background data exfiltration goes entirely unnoticed
- No user-friendly interface for allowlisting or alerting on anomalous connections

---

## 5. High-Level Solution

A **local-first agent + web dashboard system** that:

- Captures network connection metadata at the OS/kernel level (not payloads)
- Maps connections to processes in real-time using PID resolution
- Enriches data with DNS, GeoIP, ASN, and threat intelligence lookups
- Detects anomalies using a hybrid rule-based + behavioral model
- Streams insights to a responsive local dashboard
- Allows users to allowlist, block, and tune alerts with full control

---

## 6. System Architecture

```
                +----------------------+
                |   eBPF / libpcap     |
                | (Kernel-level probe) |
                +----------+-----------+
                           |
                +----------------------+
                | Event Collector      |
                | (Async ingestion)    |
                +----------+-----------+
                           |
                +----------------------+
                | Stream Processor     |
                | (Redis / Kafka)      |
                +----------+-----------+
                           |
        +------------------+------------------+
        |                                     |
+----------------------+          +----------------------+
| Enrichment Service   |          | Detection Engine     |
| - DNS cache          |          | - Rule engine        |
| - GeoIP              |          | - Baseline model     |
| - Threat intel       |          | - Anomaly scoring    |
+----------+-----------+          +----------+-----------+
           |                                 |
           +---------------+-----------------+
                           |
                +----------------------+
                | Storage Layer        |
                | - PostgreSQL         |
                | - ClickHouse (opt.)  |
                +----------+-----------+
                           |
                +----------------------+
                | API Layer            |
                | (FastAPI + gRPC)     |
                +----------+-----------+
                           |
                +----------------------+
                | Web Dashboard        |
                | (React / Next.js)    |
                +----------------------+
```

---

## 7. Core Components

### 7.1 Kernel-Level Network Capture

**Preferred:** eBPF (Linux 5.8+)
**Fallback:** libpcap / Npcap (cross-platform)

**Responsibilities:**
- Capture connection metadata only — never payloads
- Resolve PID at time of connection event
- Emit structured events to the collector

**Event schema (emitted per connection):**

```json
{
  "timestamp": "2025-06-01T10:23:45.123Z",
  "src_ip": "192.168.1.5",
  "dst_ip": "93.184.216.34",
  "src_port": 52341,
  "dst_port": 443,
  "protocol": "TCP",
  "pid": 4821,
  "process_name": "chrome",
  "process_path": "/usr/bin/google-chrome",
  "uid": 1000,
  "bytes_sent": 1240,
  "bytes_recv": 8800,
  "state": "ESTABLISHED"
}
```

**Required kernel capabilities:**
- Linux: `CAP_BPF` + `CAP_PERFMON` (kernel ≥5.8) or `CAP_SYS_ADMIN` (older)
- See Section 9 for full privilege model

---

### 7.2 Event Collector

**Role:** Async ingestion buffer between the kernel probe and the stream processor.

**Responsibilities:**
- Accept events from the kernel probe over Unix domain socket or shared memory ring buffer
- Buffer in-memory during stream processor backpressure
- Emit structured JSON to stream layer
- Drop and log events gracefully under sustained overload (configurable drop policy)

**Tech:** Go (preferred for performance) or Python with asyncio

**Failure behavior:** See Section 11.1

---

### 7.3 Stream Processing Layer

**Role:** Decouple ingestion from processing; enable horizontal scalability.

| Stage | MVP | Production |
|---|---|---|
| Stream broker | Redis Streams | Apache Kafka |
| Consumer groups | Single consumer | Multiple parallel consumers |
| Retention | 1 hour in-memory | Configurable (default 24h on disk) |
| Ordering guarantee | Per-key (src_ip) | Per-partition |

**Backpressure policy:** If consumer lag exceeds configurable threshold, the collector switches to drop-tail mode and emits a `STREAM_BACKPRESSURE` metric.

---

### 7.4 Enrichment Service

**Responsibilities:**
- Reverse DNS lookup with local TTL-respecting cache
- GeoIP lookup (MaxMind GeoLite2 — local database, updated weekly)
- ASN mapping
- Threat intelligence blocklist check (local copy, updated daily)

**Requirements:**
- All lookups async and non-blocking
- Hard timeout per lookup: 200ms (DNS), 5ms (GeoIP/ASN local DB)
- Failed lookups return `null` fields — never block the pipeline
- Cache size: configurable, default 50,000 entries (LRU eviction)

**Enriched event additions:**

```json
{
  "dst_hostname": "example.com",
  "dst_country": "US",
  "dst_asn": "AS15133",
  "dst_org": "Edgecast Inc.",
  "threat_intel": {
    "is_blocklisted": false,
    "source": null
  }
}
```

---

### 7.5 Detection Engine

#### Approach: Hybrid (Rule-Based + Behavioral)

**Rule-Based (V1 — shipped at MVP):**

| Rule ID | Description | Severity |
|---|---|---|
| R001 | Connection rate > 100/min per process | HIGH |
| R002 | Connection to known blocklisted IP/domain | CRITICAL |
| R003 | Rare port usage for process (e.g., curl on port 25) | MEDIUM |
| R004 | New external destination for process (first seen) | LOW |
| R005 | Process connecting to TOR exit node | HIGH |
| R006 | Data volume spike > 3x 7-day baseline | HIGH |
| R007 | Connection at unusual hour for process (time-of-day baseline) | MEDIUM |

**Behavioral Baseline (V2 — post-MVP):**
- Per-process rolling baseline: destination IPs, ports, data volume, connection frequency
- Deviation scoring using z-score against 7-day window
- Time-of-day awareness (separate baselines for business hours vs off-hours)
- Minimum 48 hours of history required before behavioral alerts are enabled for a process

**Alert output schema:**

```json
{
  "alert_id": "a1b2c3d4",
  "timestamp": "2025-06-01T10:23:45.123Z",
  "severity": "HIGH",
  "rule_id": "R001",
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

### 7.6 Storage Layer

**Primary:** PostgreSQL 15+

| Table | Contents | Retention Default |
|---|---|---|
| `connections` | Raw enriched connection events | 30 days |
| `alerts` | Detection engine output | 90 days |
| `processes` | Process registry (name, path, first/last seen) | Indefinite |
| `allowlist` | User-defined allow rules | Indefinite |
| `baselines` | Per-process behavioral baselines (V2) | Rolling 90 days |
| `metrics_hourly` | Aggregated hourly traffic metrics | 1 year |

**High-volume analytics (optional — V1+):** ClickHouse for `connections` table when event volume exceeds 1M/day.

**Index strategy:**
- `connections`: indexes on `(timestamp, process_name)`, `(dst_ip)`, `(pid)`
- `alerts`: indexes on `(timestamp, severity)`, `(process_name)`

---

### 7.7 API Layer

**Tech:** FastAPI (REST + WebSocket) | gRPC for internal service communication

**Auth:** JWT (HS256), issued at login, 8h expiry, refresh token support
**Rate limiting:** 100 req/min per client (REST), unlimited for authenticated WebSocket streams
**Versioning:** All endpoints prefixed `/api/v1/`

See Section 8 for full API contract.

---

### 7.8 Frontend Dashboard

**Tech:** React 18 / Next.js 14 | Recharts for data visualization

**Core screens:**

| Screen | Description |
|---|---|
| Live Feed | Real-time connection stream, filterable by process/IP/port |
| Process View | Per-app traffic breakdown, top destinations, data volume |
| Alerts | Active and historical alerts with severity, confidence, actions |
| Allowlist Manager | View, add, edit, delete allow rules |
| Baseline Explorer (V2) | Per-process behavioral baseline visualization |
| Settings | Retention config, update schedules, privilege status |

**WebSocket:** Dashboard subscribes to `/api/v1/ws/live` for real-time events. Reconnects with exponential backoff (max 30s). Displays connection status indicator.

---

## 8. API Contract

### Authentication

```
POST /api/v1/auth/login
Body: { "password": "string" }         // local single-user auth
Response 200: { "token": "jwt", "expires_at": "iso8601" }
Response 401: { "error": "INVALID_CREDENTIALS" }
```

### Connections

```
GET /api/v1/connections
Query params:
  - from        ISO8601 datetime (required)
  - to          ISO8601 datetime (required)
  - process     string (optional, filter by process name)
  - dst_ip      string (optional)
  - severity    string (optional, alert severity filter)
  - page        int (default: 1)
  - page_size   int (default: 50, max: 500)

Response 200:
{
  "data": [ <connection_object>, ... ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 4821,
    "total_pages": 97
  }
}

Response 400: { "error": "INVALID_DATE_RANGE", "message": "..." }
Response 401: { "error": "UNAUTHORIZED" }
```

### Alerts

```
GET /api/v1/alerts
Query params:
  - status      "active" | "suppressed" | "resolved" (default: "active")
  - severity    "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  - from / to   ISO8601
  - page / page_size

Response 200:
{
  "data": [ <alert_object>, ... ],
  "pagination": { ... }
}

PATCH /api/v1/alerts/:alert_id
Body: { "action": "suppress" | "resolve", "reason": "string" }
Response 200: { "alert_id": "...", "status": "suppressed" }
Response 404: { "error": "ALERT_NOT_FOUND" }
```

### Allowlist

```
GET /api/v1/allowlist
Response 200: { "data": [ <rule_object>, ... ] }

POST /api/v1/allowlist
Body:
{
  "type": "process" | "ip" | "domain" | "process_domain",
  "process_name": "string (optional)",
  "dst_ip": "string (optional)",
  "dst_domain": "string (optional)",
  "dst_port": int (optional),
  "reason": "string",
  "expires_at": "ISO8601 (optional, null = permanent)"
}
Response 201: { "rule_id": "...", ...rule }
Response 400: { "error": "INVALID_RULE", "message": "..." }

DELETE /api/v1/allowlist/:rule_id
Response 204: (no body)
Response 404: { "error": "RULE_NOT_FOUND" }
```

### Stats

```
GET /api/v1/stats/summary
Response 200:
{
  "period": "last_24h",
  "total_connections": 48210,
  "unique_destinations": 312,
  "active_alerts": 3,
  "top_processes": [
    { "name": "chrome", "connections": 12400, "bytes_sent": 2048000 }
  ],
  "top_destinations": [
    { "hostname": "google.com", "connections": 3200 }
  ]
}

GET /api/v1/stats/timeseries
Query params:
  - metric    "connections" | "bytes" | "alerts"
  - interval  "1m" | "5m" | "1h" | "1d"
  - from / to ISO8601

Response 200:
{
  "metric": "connections",
  "interval": "5m",
  "data": [ { "timestamp": "...", "value": 142 }, ... ]
}
```

### WebSocket — Live Stream

```
WS /api/v1/ws/live
Auth: ?token=<jwt> (query param)

Server emits:
{ "type": "connection", "data": <connection_object> }
{ "type": "alert",      "data": <alert_object> }
{ "type": "heartbeat",  "data": { "ts": "iso8601" } }   // every 10s

Client may send:
{ "type": "filter", "data": { "process": "chrome" } }   // applies server-side filter
```

### Error Codes Reference

| Code | HTTP Status | Meaning |
|---|---|---|
| `UNAUTHORIZED` | 401 | Missing or invalid JWT |
| `FORBIDDEN` | 403 | Token valid but insufficient scope |
| `INVALID_DATE_RANGE` | 400 | `from` after `to`, or range > 90 days |
| `INVALID_RULE` | 400 | Allowlist rule missing required fields |
| `ALERT_NOT_FOUND` | 404 | Alert ID does not exist |
| `RULE_NOT_FOUND` | 404 | Allowlist rule ID does not exist |
| `RATE_LIMITED` | 429 | Exceeded 100 req/min |
| `INTERNAL_ERROR` | 500 | Unexpected server error — check logs |

---

## 9. Privilege & Trust Model

This is a critical section. PNPG requires elevated OS privileges. How those privileges are acquired and communicated to users is a core product trust decision.

### Required Privileges by Platform

| Platform | Required Privilege | Why |
|---|---|---|
| Linux (eBPF, kernel ≥5.8) | `CAP_BPF` + `CAP_PERFMON` | Load eBPF programs and read perf events |
| Linux (eBPF, kernel <5.8) | `CAP_SYS_ADMIN` | Broader fallback — flag prominently to user |
| Linux (libpcap fallback) | `CAP_NET_RAW` | Raw packet capture |
| Windows | Administrator + Npcap driver | Kernel-level capture |
| macOS | System Extension approval | Network Extension entitlement |

### Privilege Acquisition Strategy

1. **Installer runs with elevated privilege** to install the kernel probe component.
2. **Agent daemon drops privileges** after probe is loaded — runs as a dedicated `pnpg` system user with only `CAP_NET_BIND_SERVICE` retained post-load.
3. **API and dashboard** run as unprivileged user — no root access required after install.
4. **Explicit user consent dialog** shown during install, explaining exactly what capabilities are requested and why.

### Consent Model

The installer must display a plain-language consent screen before acquiring any elevated privileges:

> *"PNPG needs to monitor network connections on this machine. To do this, it will load a kernel monitoring component that captures connection metadata (never content). This requires administrator permission during setup only. After setup, PNPG runs without administrator rights."*

User must click **Allow** to proceed. Install aborts cleanly if declined.

### Privilege Escalation Attack Surface

- Kernel probe is **read-only** — it only observes, never modifies network traffic
- eBPF programs are **verified by the kernel verifier** before loading
- No external network calls are made by any PNPG component
- Agent IPC channel (Unix socket) is permission-restricted to `pnpg` user group only

---

## 10. Data Retention & Privacy Policy

PNPG captures metadata about every outbound connection on the host. This is inherently sensitive. The following policies are non-negotiable defaults.

### Retention Defaults (User-Configurable)

| Data Type | Default Retention | Minimum | Maximum |
|---|---|---|---|
| Raw connection events | 30 days | 1 day | 365 days |
| Alerts | 90 days | 7 days | 365 days |
| Aggregated metrics | 1 year | 30 days | Indefinite |
| Process registry | Indefinite | N/A | N/A |
| Behavioral baselines | Rolling 90 days | 30 days | 180 days |

### PII Handling

- **Local IPs and PIDs** are considered sensitive — never logged to external systems
- **Process paths** may contain usernames (e.g., `/home/alice/app`) — truncated to process name in UI by default; full path stored locally only
- **DNS hostnames** resolved locally — DNS queries themselves are never forwarded to a third-party resolver by PNPG
- **No analytics, crash reporting, or telemetry** is collected or transmitted by PNPG

### Data Purge

- Automatic purge runs nightly based on configured retention windows
- Manual "Purge All Data" option available in Settings — requires confirmation
- Uninstall includes optional "Delete all PNPG data" checkbox

### Storage Encryption

- Local database encryption at rest using SQLCipher (PostgreSQL) or equivalent: **optional in MVP, enforced in V1**
- Key derived from system keychain / user password at startup

---

## 11. Failure Modes & Recovery

Production systems fail. Every component must have a defined failure behavior.

### 11.1 Kernel Probe Failure

| Failure | Detection | Recovery |
|---|---|---|
| eBPF program rejected by kernel verifier | Startup error log + UI banner | Automatic fallback to libpcap |
| eBPF probe crashes at runtime | Watchdog detects missing heartbeat within 5s | Auto-restart probe (max 3 attempts), then fallback to libpcap, then alert user |
| libpcap unavailable (no driver) | Startup check | Show onboarding error with install instructions |
| Insufficient privileges | Startup capability check | Show privilege error with remediation steps |

### 11.2 Event Collector Failure

| Failure | Detection | Recovery |
|---|---|---|
| Collector process crash | Systemd / process supervisor | Auto-restart within 2s |
| Collector queue full (sustained overload) | Queue depth metric | Drop-tail with `COLLECTOR_OVERFLOW` metric emitted; events dropped, never corrupted |
| Unix socket unavailable | Probe detects connection error | Probe buffers up to 10,000 events in ring buffer (configurable), then drops |

### 11.3 Stream Processor (Redis/Kafka) Failure

| Failure | Detection | Recovery |
|---|---|---|
| Redis/Kafka unavailable | Collector detects write failure | Collector switches to local disk buffer (configurable, default 1GB); replays when stream recovers |
| Consumer lag > threshold | Kafka consumer group lag metric | Alert emitted; detection engine may process stale events; dashboard shows "processing delay" warning |
| Broker data loss | Offset mismatch on restart | Detection engine resumes from last committed offset; gap logged |

### 11.4 Enrichment Service Failure

| Failure | Detection | Recovery |
|---|---|---|
| DNS lookup timeout | Per-lookup 200ms timeout | Return `null` for `dst_hostname`; pipeline continues |
| GeoIP database missing/stale | Startup check | Return `null` for geo fields; emit `GEOIP_STALE` metric if DB >30 days old |
| Threat intel feed unavailable | Daily update check | Use last known good copy; emit `THREATINTEL_STALE` metric |

### 11.5 Database Failure

| Failure | Detection | Recovery |
|---|---|---|
| PostgreSQL unavailable | API health check | API returns `503`; dashboard shows "storage unavailable" banner; events queue in stream layer |
| Disk full | OS-level disk monitoring | PNPG pauses writes, emits `DISK_FULL` alert, purges oldest data if auto-purge is enabled |
| Corrupted DB | pg_checksums failure | Alert user; provide restore-from-backup instructions in UI |

### 11.6 API / Dashboard Failure

| Failure | Detection | Recovery |
|---|---|---|
| API process crash | Process supervisor | Auto-restart within 2s |
| WebSocket disconnect | Client detects missed heartbeat (>15s) | Client reconnects with exponential backoff (1s, 2s, 4s … max 30s); shows reconnecting indicator |
| API returns 500 | Client error handler | Show error toast; retry with backoff |

---

## 12. False Positive Handling & Alert UX

Achieving <10% false positive rate requires both a good detection model and a user experience that lets users correct the model.

### Alert Actions

Every alert in the dashboard must offer the following user actions:

| Action | Effect |
|---|---|
| **Suppress once** | Dismiss this specific alert instance; does not affect future alerts |
| **Suppress this rule for process** | Add a scoped suppression: rule R001 will not fire for `chrome` again |
| **Allowlist destination** | Add dst_ip or dst_domain to allowlist for this process permanently |
| **Allowlist globally** | Add dst_ip or dst_domain to global allowlist (all processes) |
| **Mark as true positive** | Flags alert for baseline training (V2); increments confidence weight |

### Alert Tuning Interface

- Per-rule sensitivity sliders (threshold adjustments) in Settings > Detection
- Suppression log: full list of all suppressions, with ability to undo
- Allowlist manager: shows all rules, scope (process/global), expiry, and reason
- "Alert noise" metric on dashboard: ratio of suppressed to total alerts over 7 days

### Suppression Storage

Suppressions are stored in PostgreSQL `suppressions` table:

```
suppression_id, rule_id, process_name (nullable), dst_ip (nullable),
dst_domain (nullable), scope ("process"|"global"), created_at, expires_at (nullable),
created_by, reason
```

---

## 13. Onboarding & Installer Flow

### Linux (MVP)

```
1. User downloads pnpg-installer.sh
2. Installer checks:
   a. Kernel version (eBPF support)
   b. Available capabilities
   c. Disk space (minimum 2GB)
   d. Port 7070 (default dashboard port) available
3. Consent dialog displayed (see Section 9)
4. User approves → installer:
   a. Creates pnpg system user and group
   b. Installs kernel probe with required capabilities
   c. Installs PostgreSQL (embedded or system-level)
   d. Starts pnpg-agent, pnpg-api, pnpg-dashboard as systemd services
5. Opens browser to http://localhost:7070
6. First-run wizard:
   a. Set dashboard password
   b. Configure retention window
   c. Enable/disable threat intel feed updates
   d. Show first connections populating in real-time
```

### First-Run Experience Requirements

- Dashboard must show live data within **30 seconds** of install completing
- Process names must be resolved (not just PIDs) from first event
- A "getting started" banner guides the user to the Process View
- If eBPF fallback to libpcap occurred, a prominent but non-alarming notice explains why

### Windows (V1 Partial)

- MSI installer with UAC elevation prompt
- Npcap driver bundled or prompted for install
- Same first-run wizard as Linux

---

## 14. Data Flow

```
1.  Kernel probe captures connection event (eBPF / libpcap)
2.  Event emitted to Event Collector via Unix socket
3.  Collector buffers and publishes to stream (Redis Streams / Kafka)
4.  Enrichment Service consumes from stream:
      - DNS reverse lookup (cached)
      - GeoIP + ASN lookup (local DB)
      - Threat intel check (local blocklist)
      - Enriched event published to enriched topic
5.  Detection Engine consumes enriched topic:
      - Evaluates rule set (R001–R007+)
      - Generates alert if rule triggers
      - Checks allowlist before alerting (suppresses if allowlisted)
      - Publishes alert to alerts topic
6.  Storage Writer consumes both topics:
      - Batch-writes connections to PostgreSQL
      - Writes alerts to PostgreSQL
      - Updates process registry
7.  API layer serves:
      - REST queries against PostgreSQL
      - WebSocket stream from enriched + alerts topics (real-time)
8.  Dashboard renders:
      - Live connection feed via WebSocket
      - Historical data via REST
```

**End-to-end latency target:** Kernel event → Dashboard display < 100ms (p95)

---

## 15. Scalability Strategy

- Horizontal scaling of Enrichment Service and Detection Engine via consumer groups
- Stateless API layer — multiple instances behind NGINX load balancer
- Batch writes to PostgreSQL (configurable batch size, default 500 events per write)
- ClickHouse for `connections` table when volume exceeds 1M events/day
- Backpressure handling: collector disk buffer prevents data loss during processing lag
- Stream retention: Kafka topic retention set to 24h — allows consumer replay after recovery

---

## 16. Security Considerations

- **Least privilege:** Agent drops to unprivileged user after probe load
- **No external network calls:** All enrichment uses local databases (GeoIP, threat intel)
- **IPC hardening:** Unix socket restricted to `pnpg` group; gRPC internal channels use mTLS in production
- **API authentication:** JWT required for all endpoints; no unauthenticated access
- **Local storage encryption:** SQLCipher at rest (V1+)
- **No payload capture:** eBPF/libpcap probes capture connection metadata only — hard-coded in probe, not configurable
- **Audit log:** All allowlist changes, suppression actions, and setting changes are logged with timestamp to `audit_log` table

---

## 17. Observability

### Metrics (Prometheus)

| Metric | Type | Description |
|---|---|---|
| `pnpg_events_captured_total` | Counter | Total kernel events captured |
| `pnpg_events_dropped_total` | Counter | Events dropped due to backpressure |
| `pnpg_enrichment_latency_ms` | Histogram | Per-lookup enrichment latency |
| `pnpg_alerts_generated_total` | Counter | Alerts generated, by rule and severity |
| `pnpg_db_write_latency_ms` | Histogram | Batch write latency to PostgreSQL |
| `pnpg_stream_consumer_lag` | Gauge | Kafka/Redis consumer lag (events) |
| `pnpg_probe_status` | Gauge | 1 = eBPF active, 0.5 = libpcap fallback, 0 = down |

### Logging

- Structured JSON logs (all components)
- Log levels: DEBUG / INFO / WARN / ERROR
- Default log rotation: 100MB max, 7-day retention
- Log location: `/var/log/pnpg/`

### Internal Dashboard (Grafana)

- Pre-built Grafana dashboards for: event throughput, consumer lag, alert rate, enrichment latency
- Bundled with Docker Compose deployment

### Health Endpoints

```
GET /api/v1/health
Response 200: { "status": "ok", "probe": "ebpf|libpcap|down", "db": "ok|degraded", "stream": "ok|degraded" }
Response 503: { "status": "degraded", ... }
```

---

## 18. Deployment Architecture

### MVP — Docker Compose

```yaml
services:
  pnpg-probe:      # eBPF / libpcap kernel probe (host network + capabilities)
  pnpg-collector:  # Event collector
  pnpg-redis:      # Redis Streams (stream broker)
  pnpg-enrichment: # Enrichment service
  pnpg-detection:  # Detection engine
  pnpg-postgres:   # PostgreSQL storage
  pnpg-api:        # FastAPI REST + WebSocket
  pnpg-dashboard:  # Next.js frontend
  pnpg-nginx:      # Reverse proxy (SSL termination)
```

### Production — Kubernetes

- Each service as a Deployment with liveness + readiness probes
- HorizontalPodAutoscaler on enrichment and detection services
- PostgreSQL via managed service or StatefulSet with persistent volumes
- Kafka via managed service or Confluent operator
- Secrets via Kubernetes Secrets + optional Vault integration
- NGINX Ingress for dashboard access

### Resource Estimates (Single-Host MVP)

| Component | CPU | RAM |
|---|---|---|
| Kernel probe | <2% | 50MB |
| Collector | <1% | 100MB |
| Redis | <1% | 256MB |
| Enrichment | <3% | 256MB |
| Detection | <3% | 256MB |
| PostgreSQL | <5% | 512MB |
| API | <2% | 256MB |
| Dashboard | <1% | 128MB |
| **Total** | **<18%** | **~1.8GB** |

---

## 19. Cross-Platform Strategy

| OS | Capture Method | Status | Notes |
|---|---|---|---|
| Linux (kernel ≥5.8) | eBPF | Full support | Primary target |
| Linux (kernel <5.8) | libpcap | Full support | Fallback |
| Windows 10/11 | Npcap | Partial (V1) | No eBPF; process mapping via Win32 API |
| macOS 12+ | Network Extension | Limited (V2) | Requires Apple notarization |

---

## 20. Performance Requirements

| Metric | Target | Hard Limit |
|---|---|---|
| Event throughput | ≥10,000 events/sec | Must not drop events below 8,000/sec |
| End-to-end latency (p95) | <100ms | <250ms |
| CPU overhead (probe) | <2% | <5% |
| Total system CPU overhead | <10% | <18% |
| Memory footprint (total) | <2GB | <3GB |
| Dashboard load time (first paint) | <1.5s | <3s |
| Alert generation latency | <500ms from event | <2s |

---

## 21. Testing Strategy

### Unit Testing
- Each service module tested independently
- Coverage target: >80% on detection engine and enrichment service
- Mocked kernel events for probe unit tests

### Integration Testing
- End-to-end data flow: synthetic kernel event → alert → API → dashboard
- Allowlist suppression: alert must not appear if matching allowlist rule exists
- Failure mode tests: kill each service and verify recovery behavior per Section 11

### Load Testing
- Simulate 15,000 events/sec sustained for 10 minutes
- Verify: no event loss, consumer lag < 1,000 events, p95 latency < 150ms
- Tools: custom event generator + k6 for API load

### Security Testing
- Privilege escalation checks: verify agent cannot escalate beyond `pnpg` user
- API auth bypass attempts
- eBPF program validation: verify probe cannot write to kernel memory
- Dependency vulnerability scanning: `pip audit`, `npm audit`, `trivy` on Docker images

### Regression Testing
- Automated suite runs on every PR
- Full integration suite runs nightly
- Performance benchmarks run weekly; regression alert if >10% degradation

---

## 22. MVP vs Production Roadmap

### MVP (Q3 2025)
- Scapy/libpcap-based capture
- Python asyncio collector
- Redis Streams
- Rule-based detection (R001–R007)
- PostgreSQL storage
- FastAPI + basic React dashboard
- Docker Compose deployment
- Linux only
- Basic allowlist (domain + IP)

### V1 — Production (Q1 2026)
- eBPF capture (Linux kernel ≥5.8)
- Go-based collector
- Kafka stream broker
- PostgreSQL + ClickHouse (high-volume)
- Full API contract (Section 8)
- Complete alert UX (Section 12)
- Allowlist manager UI
- Windows partial support (Npcap)
- Storage encryption at rest
- Grafana observability dashboards

### V2 — Advanced (Q3 2026)
- Behavioral baseline model per process
- ML-based anomaly scoring
- Threat intelligence integration (MISP / OTX feeds)
- macOS support (Network Extension)
- Kubernetes deployment option
- Multi-user support (team installs)

---

## 23. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| eBPF kernel compatibility issues | High | High | libpcap fallback always available; kernel version checked at install |
| High false positive rate erodes user trust | Medium | High | Aggressive allowlisting UX; tuning interface; suppress-and-learn flow |
| Performance overhead on high-traffic hosts | Medium | High | Load testing at 15k events/sec; drop-tail with user notification |
| Cross-platform inconsistencies | High | Medium | Linux-first; explicit platform support matrix; no promises on macOS MVP |
| Privilege model misunderstood by users | Medium | High | Plain-language consent; detailed onboarding; "why does this need root?" FAQ |
| Database disk growth on busy hosts | Medium | Medium | Default 30-day retention; disk usage visible in dashboard; auto-purge |
| eBPF verifier rejects probe on custom kernels | Low | High | Automatic libpcap fallback; test matrix covers major distros |
| Dependency CVEs in third-party libraries | Medium | Medium | Automated scanning in CI; weekly dependency updates |

---

## 24. Success Metrics

| Metric | Target | Measurement Method |
|---|---|---|
| Detection accuracy | >85% true positive rate | Manual audit of 100 random alerts/week |
| False positive rate | <10% | Suppression rate as proxy; user survey |
| End-to-end latency (p95) | <100ms | Prometheus histogram |
| System CPU overhead | <10% | Prometheus node exporter |
| Dashboard time-to-first-data | <30s post-install | Automated install test |
| User retention (30-day) | >60% of installs active at 30 days | Anonymous install ping (opt-in) |
| Alert suppression rate | <25% (proxy for noise) | Suppression table / total alerts |
| Crash-free sessions | >99.5% | Error rate from structured logs |

---

*End of Document — PNPG Production PRD v1.0*