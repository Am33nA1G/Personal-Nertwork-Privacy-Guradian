# Personal Network Privacy Guardian (PNPG)

## What This Is

A real-time network monitoring system that captures outgoing traffic from a user's device, maps connections to the applications generating them, resolves IP addresses to domain names, and flags suspicious activity through rule-based anomaly detection. Everything is displayed in a clean web dashboard built for users who have no deep networking expertise.

## Core Value

Users can see exactly which apps are talking to the internet and get alerted when something looks suspicious — without needing to understand Wireshark.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Capture outgoing network packets in real-time using Scapy
- [ ] Map each connection to the originating process using psutil
- [ ] Resolve destination IPs to domain names via socket DNS lookup
- [ ] Apply rule-based anomaly detection (unknown domain, high rate, unusual port, unknown process)
- [ ] Expose live data via FastAPI REST endpoints (GET /connections, GET /alerts, GET /stats)
- [ ] Push real-time updates to the frontend via WebSocket (/ws/live)
- [ ] Display a live connections table with time, app, domain, IP, port, protocol
- [ ] Show an alerts panel highlighting suspicious activity
- [ ] Render charts for data usage per app and connections per second
- [ ] Log connections and alerts to JSON files in /logs

### Out of Scope

- Cloud deployment or remote access — runs locally only, no external data sharing
- External antivirus/threat intelligence integration — rule-based detection only for v1
- SQLite persistence — using in-memory + JSON logs initially; upgrade is deferred
- Mobile or cross-platform agent — Windows/Linux desktop only (requires admin/root)
- User authentication — local tool, no multi-user access needed

## Context

- This is a computer networking lab project built for academic/demonstration purposes
- The main challenge areas are: mapping packets to processes (Scapy captures don't carry PID — must correlate via psutil.net_connections()), real-time performance under traffic bursts, and requiring elevated privileges for packet sniffing
- Frontend connects to backend via WebSocket for live push; REST endpoints support manual queries
- Build order is intentional: verify packet capture first, then add layers (process mapping → DNS → detection → API → frontend)

## Constraints

- **Privileges**: Admin/root required — Scapy needs raw socket access
- **Tech Stack**: Python 3.10+, FastAPI, Scapy, psutil, socket, uvicorn; HTML/CSS/JS + Chart.js frontend — no framework changes
- **Local Only**: No external network calls from the tool itself; all resolution is local DNS
- **Storage**: JSON flat files for v1 — no database dependency
- **Performance**: Detection rules must be lightweight enough to not block the sniff loop

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Scapy for packet capture | Built-in Python library with rich filtering; sufficient for local monitoring | — Pending |
| psutil correlation for process mapping | No direct PID in Scapy packets — correlate via net_connections() matching local IP+port | — Pending |
| WebSocket for real-time push | REST polling would add latency; WebSocket gives instant UI updates | — Pending |
| In-memory + JSON storage | Zero-dependency storage for v1; SQLite upgrade path preserved | — Pending |
| FastAPI backend | Async-first, built-in WebSocket support, OpenAPI docs auto-generated | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-31 after initialization*
