# Requirements: Personal Network Privacy Guardian (PNPG)

**Defined:** 2026-03-31
**Core Value:** Users can see exactly which apps are talking to the internet and get alerted when something looks suspicious — without needing to understand Wireshark.

## v1 Requirements

### Capture

- [ ] **CAP-01**: System captures outgoing network packets in real-time using Scapy with `store=False` (no memory accumulation)
- [ ] **CAP-02**: System runs Npcap startup check and exits with a clear error message if Npcap is not installed
- [ ] **CAP-03**: System verifies it is running with administrator/root privileges on startup
- [ ] **CAP-04**: System auto-selects the interface with highest outbound traffic if multiple interfaces are active
- [ ] **CAP-05**: Packet sniffer runs in a dedicated daemon thread with a bounded asyncio queue (maxsize=500) bridging to FastAPI
- [ ] **CAP-06**: When the packet queue reaches max capacity, system drops oldest packets (drop-head strategy) instead of blocking
- [ ] **CAP-07**: System logs packet drops as INFO events for observability
- [ ] **CAP-08**: Each event includes both wall-clock timestamp (ISO8601) and monotonic timestamp for accurate ordering
- [ ] **CAP-09**: User can override interface selection via `config.yaml` or CLI flag
- [ ] **CAP-10**: Packet sniffer automatically restarts on failure with exponential backoff

### Process Attribution

- [ ] **PROC-01**: System maps each connection to an originating process name and PID using psutil
- [ ] **PROC-02**: psutil connection table is polled on a background schedule (200ms interval) — not called per-packet
- [ ] **PROC-03**: Connections that cannot be attributed show "unknown process" rather than failing or crashing
- [ ] **PROC-04**: System handles `AccessDenied` from psutil for system processes gracefully
- [ ] **PROC-05**: System correlates packet (src_ip, src_port) with psutil connection table using a lookup cache
- [ ] **PROC-06**: Mapping cache entries expire after configurable TTL (default: 2 seconds) to prevent stale attribution

### DNS Resolution

- [ ] **DNS-01**: System resolves destination IPs to domain names via reverse DNS lookup
- [ ] **DNS-02**: DNS lookups run in a thread pool executor (not blocking the event loop)
- [ ] **DNS-03**: DNS resolution has a 2-second timeout per lookup to prevent pipeline stall
- [ ] **DNS-04**: Resolved IP→domain mappings are cached with TTL to avoid repeated lookups for the same destination
- [ ] **DNS-05**: Unresolvable IPs fall back to displaying raw IP address

### Detection

- [ ] **DET-01**: System flags connections with no resolvable domain as WARNING
- [ ] **DET-02**: System flags connections whose rate exceeds a configurable threshold (default: 50/sec) as ALERT
- [ ] **DET-03**: System flags connections on ports outside allowlist [80, 443, 53, 123, 5353, 8080, 8443] only if also combined with unknown process or abnormal frequency (avoids false-positive flooding)
- [ ] **DET-04**: System flags connections from an unknown process as ALERT
- [ ] **DET-05**: Detection thresholds are named constants (not magic numbers) in `config.yaml`
- [ ] **DET-06**: Detection engine rate-limits alerts to max 1 alert per rule per second to prevent alert flooding

### Storage

- [ ] **STORE-01**: Active connections are kept in a bounded in-memory deque (maxsize=1000)
- [ ] **STORE-02**: Connections are logged to `logs/connections.ndjson` in NDJSON format (one JSON object per line — corruption-safe)
- [ ] **STORE-03**: Alerts are logged to `logs/alerts.ndjson` in NDJSON format
- [ ] **STORE-04**: Log files rotate or cap at a configurable size to prevent unbounded disk growth
- [ ] **STORE-05**: Duplicate connections within a 1-second window are aggregated into a single record with a `count` field
- [ ] **STORE-06**: Each log entry includes a unique `event_id` (UUID) for traceability
- [ ] **STORE-07**: Each log entry includes a `severity` field (INFO, WARNING, ALERT)

### Backend API

- [ ] **API-01**: `GET /connections` returns the last N live connections with app, domain, IP, port, protocol, timestamp
- [ ] **API-02**: `GET /alerts` returns active alerts with severity, rule, and connection context
- [ ] **API-03**: `GET /stats` returns aggregate stats: connections per app, total bytes (estimated), connections per second
- [ ] **API-04**: `GET /status` returns capture status (running/stopped), interface name, uptime
- [ ] **API-05**: `WebSocket /ws/live` pushes batched updates every 500ms (not per-packet) to all connected clients
- [ ] **API-06**: WebSocket manager handles client disconnections without crashing the broadcast loop
- [ ] **API-07**: FastAPI app uses lifespan context manager (not deprecated `on_event`) to start/stop the sniffer thread
- [ ] **API-08**: WebSocket batches are capped at a maximum of 100 events per push
- [ ] **API-09**: If a client cannot keep up, server drops older buffered updates rather than buffering indefinitely
- [ ] **API-10**: API response and documentation explicitly note that byte counts are estimated from packet size, not full stream reconstruction

### Configuration

- [ ] **CONFIG-01**: All thresholds and runtime settings stored in `config.yaml` (queue size, polling interval, alert rate limit, port allowlist, log rotation size)
- [ ] **CONFIG-02**: Config is validated at startup with sensible defaults applied for any missing keys
- [ ] **CONFIG-03**: System logs all critical errors without terminating the main event loop

### System Reliability

- [ ] **SYS-01**: System logs all critical errors without terminating the main event loop
- [ ] **SYS-02**: Graceful shutdown flushes all in-memory data to disk before exit

### Frontend Dashboard

- [ ] **UI-01**: Live connections table with columns: Time, App, Domain, IP, Port, Protocol, Flag
- [ ] **UI-02**: Alerts panel that highlights suspicious activity with severity color coding
- [ ] **UI-03**: Chart: data connections per app (bar or donut)
- [ ] **UI-04**: Chart: connections per second over time (line chart, rolling 60s window)
- [ ] **UI-05**: Capture status indicator showing whether sniffing is active
- [ ] **UI-06**: Frontend connects to WebSocket and updates table/charts on each batch push
- [ ] **UI-07**: Frontend does not re-render the entire DOM on every update (only delta updates)

## v2 Requirements

### Enhanced Detection

- **EDET-01**: Geolocation lookup for destination IPs (country/ASN display)
- **EDET-02**: Persistent baseline learning — flag deviations from historical normal
- **EDET-03**: User-defined allowlist (whitelist specific apps or domains from alerts)

### Storage Upgrade

- **STRE-01**: SQLite backend for querying historical connection data
- **STRE-02**: Export connections to CSV

### UI Enhancements

- **UIX-01**: Filter connections by app, domain, or protocol
- **UIX-02**: Click a connection to see detailed view with all attributes
- **UIX-03**: Dark mode

## Out of Scope

| Feature | Reason |
|---------|--------|
| Firewall / packet blocking | OS-level enforcement, requires kernel drivers — far beyond scope |
| HTTPS payload decryption | Requires MITM certificate injection — security risk and legal complexity |
| Threat intelligence API integration | External service dependency, adds cloud call; v1 is local-only |
| Cloud deployment / remote access | Runs locally only by design; admin privileges cannot be delegated remotely |
| Mobile app | Web dashboard is sufficient for local monitoring use case |
| Multi-user access / authentication | Local single-user tool |
| Inbound traffic monitoring | PRD scope is outgoing traffic; bidirectional adds complexity for limited academic value |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CAP-01 | Phase 1 | Pending |
| CAP-02 | Phase 1 | Pending |
| CAP-03 | Phase 1 | Pending |
| CAP-04 | Phase 1 | Pending |
| CAP-05 | Phase 1 | Pending |
| CAP-06 | Phase 1 | Pending |
| CAP-07 | Phase 1 | Pending |
| CAP-08 | Phase 1 | Pending |
| CAP-09 | Phase 1 | Pending |
| CAP-10 | Phase 1 | Pending |
| PROC-01 | Phase 2 | Pending |
| PROC-02 | Phase 2 | Pending |
| PROC-03 | Phase 2 | Pending |
| PROC-04 | Phase 2 | Pending |
| PROC-05 | Phase 2 | Pending |
| PROC-06 | Phase 2 | Pending |
| DNS-01 | Phase 3 | Pending |
| DNS-02 | Phase 3 | Pending |
| DNS-03 | Phase 3 | Pending |
| DNS-04 | Phase 3 | Pending |
| DNS-05 | Phase 3 | Pending |
| DET-01 | Phase 4 | Pending |
| DET-02 | Phase 4 | Pending |
| DET-03 | Phase 4 | Pending |
| DET-04 | Phase 4 | Pending |
| DET-05 | Phase 4 | Pending |
| DET-06 | Phase 4 | Pending |
| CONFIG-01 | Phase 1 | Pending |
| CONFIG-02 | Phase 1 | Pending |
| SYS-01 | Phase 1 | Pending |
| SYS-02 | Phase 5 | Pending |
| STORE-01 | Phase 5 | Pending |
| STORE-02 | Phase 5 | Pending |
| STORE-03 | Phase 5 | Pending |
| STORE-04 | Phase 5 | Pending |
| STORE-05 | Phase 5 | Pending |
| STORE-06 | Phase 5 | Pending |
| STORE-07 | Phase 5 | Pending |
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
| UI-01 | Phase 6 | Pending |
| UI-02 | Phase 6 | Pending |
| UI-03 | Phase 6 | Pending |
| UI-04 | Phase 6 | Pending |
| UI-05 | Phase 6 | Pending |
| UI-06 | Phase 6 | Pending |
| UI-07 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 55 total
- Mapped to phases: 55
- Unmapped: 0 ✓

## Data Model

### Connection Object
```json
{
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "process": "chrome.exe",
  "pid": 1234,
  "src_ip": "192.168.1.5",
  "dst_ip": "142.250.183.14",
  "domain": "google.com",
  "port": 443,
  "protocol": "TCP",
  "bytes": 1500,
  "flag": "INFO",
  "count": 1
}
```

### Alert Object
```json
{
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "severity": "ALERT",
  "rule": "DET-02",
  "message": "High connection rate detected",
  "connection_ref": "event_id"
}
```

## Known Limitations

- Packet-to-process mapping is best-effort; very short-lived connections may not be attributable
- Reverse DNS may not resolve all IPs accurately (no PTR records)
- Byte tracking is approximate (packet-level, not full TCP stream reconstruction)
- High traffic environments may result in dropped packets due to bounded queue backpressure

---
*Requirements defined: 2026-03-31*
*Last updated: 2026-03-31 after user additions (PROC-05/06, CAP-06–10, DET-06, STORE-05–07, API-08–10, CONFIG, SYS)*
